#!/usr/bin/env python3
"""Executor opt-in do protocolo de jobs da Station.

O cliente só reivindica jobs para os quais o operador deu permissão explícita:
``--allow-command`` para um comando único e ``--allow-game-dev`` para uma
sequência de testes/builds com coleta de artefatos. O token autentica o worker,
mas não transforma telemetria em shell. Cada processo recebe heartbeat e o
resultado diz o que foi observado; não promete qualidade visual ou jogabilidade.

Exemplo de comando:
  python3 arkher_station_worker.py --agent http://127.0.0.1:8765 \
      --token "$ARKHER_AGENT_TOKEN" --allow-command

Um job game-dev usa payload.motor, payload.project, payload.steps e
payload.artifacts. Os artefatos são copiados para
$ARKHER_STATE/work/station-artifacts/<job-id> por padrão e o resultado devolve
sha256, tamanho e caminho relativo para o agente servir pelo endpoint /file.
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    OUTPUT_CAPTURE = max(64 * 1024, min(8 * 1024 * 1024,
                         int(os.environ.get('ARKHER_OUTPUT_CAPTURE', str(2 * 1024 * 1024)))))
except Exception:
    OUTPUT_CAPTURE = 2 * 1024 * 1024


class StationRejected(RuntimeError):
    pass


class StationClient:
    def __init__(self, base, token):
        self.base = str(base or '').rstrip('/')
        self.token = str(token or '')
        self.worker_id = ''

    def request(self, path, method='GET', body=None):
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode('utf-8')
        if len(data or b'') > 8 * 1024 * 1024:
            raise RuntimeError('request do worker excede 8 MB')
        headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + self.token}
        if data is not None:
            headers['Content-Type'] = 'application/json'
        last = None
        for attempt in range(4):
            req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=15) as res:
                    raw = res.read(8 * 1024 * 1024 + 1)
                    if len(raw) > 8 * 1024 * 1024:
                        raise RuntimeError('resposta do agente excede 8 MB')
                    out = json.loads(raw.decode('utf-8'))
                if not out.get('ok', False):
                    raise StationRejected(out.get('err') or 'worker recusou a chamada')
                return out
            except urllib.error.HTTPError as exc:
                try:
                    raw = exc.read(256 * 1024)
                    out = json.loads(raw.decode('utf-8'))
                except Exception:
                    out = {}
                # Erros de autenticação/lease/validação não ficam sendo
                # repetidos; falhas 5xx podem ser só uma reinicialização.
                if exc.code < 500:
                    raise RuntimeError(out.get('err') or ('HTTP %s' % exc.code))
                last = RuntimeError(out.get('err') or ('HTTP %s' % exc.code))
            except StationRejected:
                raise
            except (urllib.error.URLError, TimeoutError, OSError, RuntimeError, ValueError) as exc:
                last = exc
            if attempt < 3:
                time.sleep(0.5 * (2 ** attempt))
        raise RuntimeError(str(last or 'falha de rede'))

    def identify(self):
        out = self.request('/station')
        self.worker_id = str((out.get('worker') or {}).get('id') or '')
        if not self.worker_id:
            raise RuntimeError('worker não devolveu identidade')
        return self.worker_id

    def next(self, kinds):
        qs = {'workerId': self.worker_id}
        if kinds:
            qs['kinds'] = ','.join(kinds)
        out = self.request('/station/job/next?' + urllib.parse.urlencode(qs))
        return out.get('job')

    def heartbeat(self, job, progress=None, message=''):
        body = {'jobId': job['id'], 'leaseToken': job['leaseToken']}
        if progress is not None:
            body['progress'] = progress
        if message:
            body['message'] = message[:240]
        return self.request('/station/job/heartbeat', 'POST', body).get('job')

    def complete(self, job, status, result):
        return self.request('/station/job/complete', 'POST', {
            'jobId': job['id'], 'leaseToken': job['leaseToken'],
            'status': status, 'result': result,
        }).get('job')


def _tail(text, limit=8000):
    return str(text or '')[-limit:]


def _inside_workspace(path, workspace):
    if not workspace:
        return True
    try:
        root = os.path.realpath(os.path.abspath(workspace))
        candidate = os.path.realpath(os.path.abspath(path))
        return os.path.commonpath([root, candidate]) == root
    except Exception:
        return False


def _workspace_error(path, workspace):
    if workspace and not _inside_workspace(path, workspace):
        return 'caminho fora do workspace autorizado: ' + str(path)[:240]
    return ''


def _terminate_process(proc):
    if not proc or proc.poll() is not None:
        return
    try:
        if os.name != 'nt':
            os.killpg(proc.pid, signal.SIGTERM)
        else:
            taskkill = shutil.which('taskkill') or 'taskkill.exe'
            subprocess.run([taskkill, '/PID', str(proc.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            if proc.poll() is None: proc.kill()
    except Exception:
        try: proc.kill()
        except Exception: pass


def _heartbeat_thread(client, job, stop, errors, cancelled=None):
    # O lease padrão é 120 s; renovar a cada 20 s deixa margem para chamada
    # lenta sem manter um job vivo depois que o processo acabou.
    while not stop.wait(20):
        try:
            client.heartbeat(job, message='processo ainda ativo')
        except Exception as exc:
            msg = str(exc)[:240]
            errors.append(msg)
            del errors[:-10]
            # Cancelamento revoga a lease no servidor. Interromper o processo
            # local evita continuar consumindo CPU/GPU depois de o operador
            # cancelar; falhas de rede transitórias continuam sendo tentadas.
            if cancelled is not None and any(x in msg.lower() for x in ('lease inválido', 'lease expirado', 'cancelado')):
                cancelled.set()
                return
            continue


def _run_process(client, job, cmd, cwd=None, timeout=600, label='processo'):
    """Executa um passo com saída limitada e término por prazo.

    A confirmação final fica no chamador: um game-dev com artefato esperado
    ausente não vira sucesso só porque o comando terminou com código zero. A
    saída pode ser enorme (compiladores/renderizadores); por isso só mantemos
    os últimos OUTPUT_CAPTURE bytes em memória.
    """
    cmd = str(cmd or '').strip()
    if not cmd:
        return {'executed': False, 'verified': False, 'exitCode': 125,
                'error': 'comando vazio', 'label': label}
    if cwd and not os.path.isdir(cwd):
        return {'executed': False, 'verified': False, 'exitCode': 125,
                'error': 'cwd não existe: ' + str(cwd)[:240], 'label': label}
    try:
        timeout = max(1, min(3600, int(timeout or 600)))
    except Exception:
        timeout = 600
    started = time.time()
    proc = None
    stop = threading.Event()
    cancelled = threading.Event()
    beat_errors = []
    captured = bytearray()
    output_size = [0]
    reader_errors = []
    thread = threading.Thread(target=_heartbeat_thread,
                              args=(client, job, stop, beat_errors, cancelled), daemon=True)
    reader = None

    def read_output():
        try:
            while True:
                chunk = proc.stdout.read(64 * 1024)
                if not chunk:
                    break
                raw = chunk.encode('utf-8', 'replace')
                output_size[0] += len(raw)
                captured.extend(raw)
                if len(captured) > OUTPUT_CAPTURE:
                    del captured[:-OUTPUT_CAPTURE]
        except Exception as exc:
            reader_errors.append(str(exc)[:200])

    try:
        kwargs = {'shell': True, 'cwd': cwd or None, 'stdout': subprocess.PIPE,
                  'stderr': subprocess.STDOUT, 'text': True, 'errors': 'replace'}
        if os.name != 'nt':
            kwargs['start_new_session'] = True
        elif hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP'):
            kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        proc = subprocess.Popen(cmd, **kwargs)
        thread.start()
        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        deadline = time.monotonic() + timeout
        timed_out = False
        cancelled_local = False
        while proc.poll() is None:
            if cancelled.is_set():
                cancelled_local = True
                _terminate_process(proc)
                break
            if time.monotonic() >= deadline:
                timed_out = True
                _terminate_process(proc)
                break
            time.sleep(.05)
        if timed_out or cancelled_local:
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _terminate_process(proc)
                proc.wait(timeout=5)
            code = 130 if cancelled_local else 124
        else:
            code = proc.returncode
        if reader:
            reader.join(timeout=5)
        output = bytes(captured).decode('utf-8', 'replace')
        result = {
            'label': label,
            'executed': True,
            'verified': code == 0 and not timed_out,
            'exitCode': code,
            'outputSize': output_size[0],
            'outputCaptured': len(captured),
            'outputTruncated': output_size[0] > len(captured),
            'outputTail': _tail(output),
            'durationMs': int((time.time() - started) * 1000),
            'observation': 'processo terminou com código %s' % code,
        }
        if timed_out:
            result['timedOut'] = True
            result['error'] = 'tempo esgotado'
        if cancelled_local:
            result['cancelled'] = True
            result['error'] = 'job cancelado ou lease revogada'
        if beat_errors:
            result['heartbeatError'] = beat_errors[-1]
        if reader_errors:
            result['readerError'] = reader_errors[-1]
        return result
    except Exception as exc:
        return {
            'label': label, 'executed': bool(proc), 'verified': False,
            'exitCode': 125, 'error': str(exc)[:300],
            'durationMs': int((time.time() - started) * 1000),
        }
    finally:
        stop.set()
        thread.join(timeout=2)
        if proc and proc.stdout:
            try: proc.stdout.close()
            except Exception: pass
        if reader:
            reader.join(timeout=1)
        if proc and proc.poll() is None:
            _terminate_process(proc)


def execute_command(client, job, payload, workspace=None):
    payload = payload if isinstance(payload, dict) else {}
    cmd = str(payload.get('cmd') or '').strip()
    cwd = payload.get('cwd') or workspace
    problem = _workspace_error(cwd or os.getcwd(), workspace)
    if problem:
        result = {'executed': False, 'verified': False, 'exitCode': 126,
                  'error': problem, 'label': 'command'}
    else:
        result = _run_process(client, job, cmd, cwd, payload.get('timeout') or 600, 'command')
    status = 'completed' if result.get('verified') else 'failed'
    client.complete(job, status, result)
    print('[job %s] terminou code=%s verified=%s' %
          (job['id'], result.get('exitCode'), result.get('verified')), flush=True)
    return status == 'completed'


def _artifact_root(cli_root):
    root = cli_root or os.environ.get('ARKHER_STATION_ARTIFACT_ROOT', '')
    if not root:
        state = os.environ.get('ARKHER_STATE', '')
        root = os.path.join(state, 'work', 'station-artifacts') if state else os.path.join(os.getcwd(), 'arkher-station-artifacts')
    os.makedirs(root, exist_ok=True)
    return os.path.abspath(root)


def _artifact_relpath(path):
    state = os.environ.get('ARKHER_STATE', '')
    work = os.path.join(state, 'work') if state else ''
    if work:
        try:
            rel = os.path.relpath(path, os.path.abspath(work))
            if not rel.startswith('..'):
                return rel.replace(os.sep, '/')
        except Exception:
            pass
    return os.path.abspath(path)


def collect_artifacts(job, requested, project, root):
    """Copia arquivos esperados para o workspace servido pelo agent e mede-os."""
    requested = requested if isinstance(requested, list) else []
    job_dir = os.path.join(root, re.sub(r'[^A-Za-z0-9_.-]', '_', str(job['id']))[:100])
    os.makedirs(job_dir, exist_ok=True)
    project = os.path.abspath(project or os.getcwd())
    project_real = os.path.realpath(project)
    total = 0
    try:
        max_each = max(1024 * 1024, min(2 * 1024 * 1024 * 1024,
            int(os.environ.get('ARKHER_MAX_ARTIFACT_BYTES', str(100 * 1024 * 1024)))))
        max_total = max(max_each, min(4 * 1024 * 1024 * 1024,
            int(os.environ.get('ARKHER_MAX_ARTIFACT_TOTAL', str(250 * 1024 * 1024)))))
    except Exception:
        max_each, max_total = 100 * 1024 * 1024, 250 * 1024 * 1024
    out = []
    for raw in requested[:40]:
        label = str(raw)[:400] if not isinstance(raw, dict) else str(raw.get('path') or raw.get('name') or '')[:400]
        if not label:
            continue
        source = label if os.path.isabs(label) else os.path.join(project, label)
        source = os.path.abspath(source)
        source_real = os.path.realpath(source)
        inside = False
        try:
            inside = os.path.commonpath([project_real, source_real]) == project_real
        except Exception:
            inside = False
        item = {'name': label, 'exists': os.path.exists(source) and inside, 'copied': False}
        if not inside:
            item['error'] = 'artefato fora do projeto autorizado'
            out.append(item)
            continue
        if not os.path.isfile(source):
            if os.path.isdir(source):
                try:
                    item['directory'] = True
                    item['entries'] = sum(len(files) for _root, _dirs, files in os.walk(source))
                except Exception:
                    item['entries'] = 0
            out.append(item)
            continue
        try:
            size = os.path.getsize(source)
        except OSError as exc:
            item['error'] = str(exc)[:200]
            out.append(item)
            continue
        item['size'] = size
        if size > max_each or total + size > max_total:
            item['error'] = 'limite de coleta de artefatos excedido'
            out.append(item)
            continue
        name = os.path.basename(source) or 'artifact.bin'
        dest = os.path.join(job_dir, name)
        if os.path.exists(dest):
            dest = os.path.join(job_dir, '%d-%s' % (len(out) + 1, name))
        try:
            if os.path.abspath(source) != os.path.abspath(dest):
                shutil.copy2(source, dest)
            copied_size = os.path.getsize(dest)
            if copied_size > max_each or total + copied_size > max_total:
                try: os.remove(dest)
                except Exception: pass
                item['error'] = 'limite de coleta de artefatos excedido'
                out.append(item)
                continue
            digest = hashlib.sha256()
            with open(dest, 'rb') as f:
                while True:
                    block = f.read(1024 * 1024)
                    if not block:
                        break
                    digest.update(block)
            item.update({'path': _artifact_relpath(dest), 'sha256': digest.hexdigest(),
                         'copied': True, 'size': os.path.getsize(dest)})
            total += item['size']
        except Exception as exc:
            item['error'] = str(exc)[:240]
        out.append(item)
    return out


def _quote_arg(value):
    """Citação para o shell do worker sem transformar o caminho do projeto em
    parte da sintaxe. O agente continua exigindo autorização explícita para
    executar o job; isto só impede espaços/metacaracteres de quebrarem o
    comando gerado pela receita."""
    value = str(value)
    return subprocess.list2cmdline([value]) if os.name == 'nt' else shlex.quote(value)


def _relative_to_project(path, project):
    try:
        rel = os.path.relpath(os.path.abspath(path), os.path.abspath(project))
        return rel if rel != '.' else os.path.basename(path)
    except Exception:
        return os.path.basename(str(path))


def game_dev_recipe(motor, project, payload=None):
    """Monta steps honestos para os cinco motores conhecidos.

    A receita só descreve o comando; ela não afirma que o executável está
    instalado. A execução e o log real continuam sendo responsabilidade de
    _run_process. Roblox não recebe uma falsa receita headless: Studio exige
    sessão/login, então o chamador precisa fornecer steps GUI autorizados.
    """
    payload = payload if isinstance(payload, dict) else {}
    motor = str(motor or '').lower()
    project = os.path.abspath(str(project or os.getcwd()))
    action = str(payload.get('action') or 'verify').lower()
    if motor not in ('roblox', 'godot', 'unity', 'unreal', 'blender'):
        return {'ok': False, 'error': 'motor game-dev inválido: ' + motor[:80]}
    if motor == 'roblox':
        return {'ok': False, 'error': 'Roblox Studio exige sessão gráfica e login manual; forneça payload.steps autorizados',
                'needsGui': True, 'motor': motor, 'action': action}

    steps = []
    artifacts = list(payload.get('artifacts') or []) if isinstance(payload.get('artifacts'), list) else []
    if motor == 'godot':
        if action in ('export', 'android', 'build'):
            target = str(payload.get('output') or os.path.join(project, 'build', 'jogo.apk'))
            steps.append({'name': 'godot-export',
                          'cmd': 'godot --headless --path %s --export-release "Android" %s' %
                                 (_quote_arg(project), _quote_arg(target)), 'cwd': project,
                          'timeout': payload.get('timeout', 900)})
            if not artifacts:
                artifacts.append(_relative_to_project(target, project))
        else:
            steps.append({'name': 'godot-headless-test',
                          'cmd': 'godot --headless --path %s --quit-after 2' % _quote_arg(project),
                          'cwd': project, 'timeout': payload.get('timeout', 300)})
    elif motor == 'blender':
        if action in ('render', 'renderizar'):
            blend = str(payload.get('blend') or os.path.join(project, 'cena.blend'))
            frame = str(payload.get('frame') or 1)
            output = str(payload.get('output') or os.path.join(project, 'render', 'frame_'))
            steps.append({'name': 'blender-render',
                          'cmd': 'blender -b %s -o %s -f %s' %
                                 (_quote_arg(blend), _quote_arg(output), _quote_arg(frame)),
                          'cwd': project, 'timeout': payload.get('timeout', 1800)})
            if not artifacts:
                artifacts.append(_relative_to_project(output + ('%04d.png' % int(frame)), project))
        else:
            script = str(payload.get('script') or os.path.join(project, 'scripts', 'cena.py'))
            steps.append({'name': 'blender-background-test',
                          'cmd': 'blender -b --python %s' % _quote_arg(script),
                          'cwd': project, 'timeout': payload.get('timeout', 600)})
    elif motor == 'unity':
        log = str(payload.get('log') or os.path.join(project, 'Logs', 'saida.log'))
        method = 'Build.Android' if action in ('export', 'android', 'build') else 'Build.Testar'
        steps.append({'name': 'unity-batch-test' if method == 'Build.Testar' else 'unity-build',
                      'cmd': 'unity -batchmode -nographics -quit -projectPath %s -logFile %s -executeMethod %s' %
                             (_quote_arg(project), _quote_arg(log), method),
                      'cwd': project, 'timeout': payload.get('timeout', 1800)})
        if payload.get('includeLog', True) and not artifacts:
            artifacts.append(_relative_to_project(log, project))
        if action in ('export', 'android', 'build') and payload.get('output'):
            artifacts.append(_relative_to_project(payload['output'], project))
    elif motor == 'unreal':
        project_file = str(payload.get('projectFile') or project)
        if action in ('build', 'export'):
            output = str(payload.get('output') or os.path.join(project, 'build'))
            cmd = 'RunUAT.bat BuildCookRun -project=%s -build -cook -stage -pak -archive -archivedirectory=%s' % (
                _quote_arg(project_file), _quote_arg(output))
            steps.append({'name': 'unreal-build', 'cmd': cmd, 'cwd': project,
                          'timeout': payload.get('timeout', 3600)})
            if not artifacts and payload.get('artifact'):
                artifacts.append(payload['artifact'])
        else:
            log = str(payload.get('log') or os.path.join(project, 'Saved', 'Logs', 'Jogo.log'))
            steps.append({'name': 'unreal-commandlet-test',
                          'cmd': 'UnrealEditor-Cmd.exe %s -game -nullrhi -log -stdout -ExecCmds="quit"' %
                                 _quote_arg(project_file), 'cwd': project,
                          'timeout': payload.get('timeout', 1800)})
            if payload.get('includeLog', True) and not artifacts:
                artifacts.append(_relative_to_project(log, project))
    return {'ok': True, 'motor': motor, 'action': action, 'steps': steps, 'artifacts': artifacts}


def execute_game_dev(client, job, payload, artifact_root, workspace=None):
    payload = payload if isinstance(payload, dict) else {}
    motor = str(payload.get('motor') or '').lower()
    if motor not in ('roblox', 'godot', 'unity', 'unreal', 'blender'):
        result = {'executed': False, 'verified': False,
                  'error': 'motor game-dev inválido: ' + motor[:80]}
        client.complete(job, 'failed', result)
        return False
    project = str(payload.get('project') or payload.get('cwd') or workspace or os.getcwd())
    project_problem = _workspace_error(project, workspace)
    if project_problem:
        result = {'executed': False, 'verified': False, 'motor': motor,
                  'error': project_problem}
        client.complete(job, 'failed', result)
        return False
    steps = payload.get('steps')
    recipe = {'name': 'explicit', 'action': str(payload.get('action') or 'custom')}
    requested_artifacts = payload.get('artifacts')
    if not isinstance(steps, list) or not steps:
        if payload.get('cmd'):
            steps = [{'name': 'run', 'cmd': payload.get('cmd'), 'cwd': project,
                      'timeout': payload.get('timeout', 600)}]
        else:
            recipe = game_dev_recipe(motor, project, payload)
            if not recipe.get('ok'):
                result = {'executed': False, 'verified': False, 'motor': motor,
                          'action': payload.get('action') or 'verify', 'recipe': recipe,
                          'error': recipe.get('error') or 'receita não disponível'}
                client.complete(job, 'failed', result)
                return False
            steps = recipe['steps']
            requested_artifacts = recipe.get('artifacts') or []
    if len(steps) > 20:
        result = {'executed': False, 'verified': False, 'motor': motor,
                  'error': 'limite de 20 steps excedido; nada foi executado'}
        client.complete(job, 'failed', result)
        return False
    if isinstance(requested_artifacts, list) and len(requested_artifacts) > 40:
        result = {'executed': False, 'verified': False, 'motor': motor,
                  'error': 'limite de 40 artefatos excedido; nada foi executado'}
        client.complete(job, 'failed', result)
        return False
    records = []
    for index, raw in enumerate(steps):
        step = raw if isinstance(raw, dict) else {'cmd': raw}
        name = str(step.get('name') or ('step-%d' % (index + 1)))[:100]
        step_cwd = step.get('cwd') or project
        path_problem = _workspace_error(step_cwd, workspace)
        if path_problem:
            record = {'label': name, 'executed': False, 'verified': False,
                      'exitCode': 126, 'error': path_problem}
        else:
            record = _run_process(client, job, step.get('cmd'), step_cwd,
                                  step.get('timeout') or payload.get('timeout') or 600, name)
        records.append(record)
        if not record.get('verified'):
            result = {'executed': any(x.get('executed') for x in records), 'verified': False,
                      'motor': motor, 'project': project, 'failedStep': name, 'steps': records,
                      'recipe': recipe, 'artifacts': collect_artifacts(job, requested_artifacts, project, artifact_root)}
            client.complete(job, 'failed', result)
            print('[job %s] game-dev falhou no passo %s' % (job['id'], name), flush=True)
            return False
    artifacts = collect_artifacts(job, requested_artifacts, project, artifact_root)
    missing = [x['name'] for x in artifacts if not x.get('exists') or (x.get('size', 0) and not x.get('copied'))]
    verified = all(x.get('verified') for x in records) and not missing
    result = {'executed': True, 'verified': verified, 'motor': motor, 'action': recipe.get('action'),
              'project': project, 'recipe': recipe, 'steps': records, 'artifacts': artifacts}
    if missing:
        result['error'] = 'artefato esperado não encontrado/coletado: ' + ', '.join(missing[:8])
    client.complete(job, 'completed' if verified else 'failed', result)
    print('[job %s] game-dev motor=%s verified=%s artifacts=%s' %
          (job['id'], motor, verified, len(artifacts)), flush=True)
    return verified


def handle(client, job, options):
    payload = job.get('payload') if isinstance(job.get('payload'), dict) else {}
    if job.get('kind') == 'command' and options.get('allow_command'):
        return execute_command(client, job, payload, options.get('workspace'))
    if job.get('kind') == 'game-dev' and options.get('allow_game_dev'):
        return execute_game_dev(client, job, payload, options.get('artifact_root'), options.get('workspace'))
    result = {'executed': False, 'verified': False,
              'error': 'executor não habilitado para kind=' + str(job.get('kind') or '')[:80]}
    client.complete(job, 'failed', result)
    return False


def main(argv=None):
    ap = argparse.ArgumentParser(description='executor opt-in de jobs Station')
    ap.add_argument('--agent', required=True, help='URL do agente, por exemplo http://127.0.0.1:8765')
    ap.add_argument('--token', default=os.environ.get('ARKHER_AGENT_TOKEN', ''), help='ARKHER_AGENT_TOKEN')
    ap.add_argument('--poll', type=float, default=3, help='segundos entre polls')
    ap.add_argument('--once', action='store_true', help='faz um poll e sai se não houver job')
    ap.add_argument('--allow-command', action='store_true', help='habilita kind=command')
    ap.add_argument('--allow-game-dev', action='store_true', help='habilita kind=game-dev e coleta de artefatos')
    ap.add_argument('--artifact-root', default='', help='pasta de cópia dos artefatos; padrão: ARKHER_STATE/work/station-artifacts')
    ap.add_argument('--workspace', default=os.environ.get('ARKHER_WORKSPACE', ''),
                    help='raiz obrigatória para cwd/projeto/artefatos; recomendado para isolamento')
    ap.add_argument('--kinds', default='', help='filtro opcional, por exemplo command,game-dev')
    args = ap.parse_args(argv)
    if not args.token:
        ap.error('--token ou ARKHER_AGENT_TOKEN é obrigatório')
    permitted = []
    if args.allow_command:
        permitted.append('command')
    if args.allow_game_dev:
        permitted.append('game-dev')
    if args.kinds:
        requested = [x.strip() for x in args.kinds.split(',') if x.strip()]
        permitted = [x for x in requested if x in permitted]
    if not permitted:
        print('nada executado: habilite --allow-command e/ou --allow-game-dev', flush=True)
        return 2
    workspace = os.path.abspath(os.path.expanduser(args.workspace)) if args.workspace else ''
    if workspace and not os.path.isdir(workspace):
        ap.error('--workspace não existe: ' + workspace)
    client = StationClient(args.agent, args.token)
    try:
        client.identify()
    except Exception as exc:
        print('worker indisponível: %s' % exc, flush=True)
        return 1
    options = {'allow_command': args.allow_command, 'allow_game_dev': args.allow_game_dev,
               'artifact_root': _artifact_root(args.artifact_root), 'workspace': workspace}
    while True:
        try:
            job = client.next(permitted)
            if not job:
                if args.once:
                    print('fila vazia: nada executado', flush=True)
                    return 0
                time.sleep(max(.5, min(60, args.poll)))
                continue
            ok = handle(client, job, options)
            if args.once:
                return 0 if ok else 1
        except KeyboardInterrupt:
            return 130
        except Exception as exc:
            print('poll/execução: %s' % exc, flush=True)
            if args.once:
                return 1
            time.sleep(max(.5, min(60, args.poll)))


if __name__ == '__main__':
    raise SystemExit(main())
