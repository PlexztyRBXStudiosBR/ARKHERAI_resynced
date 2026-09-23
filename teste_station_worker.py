#!/usr/bin/env python3
"""Integração do protocolo Station -> worker autorizado.

O teste usa somente a stdlib e uma instância local efêmera do agent.py. Ele não
executa comando recebido: valida a parte que precisa ser confiável antes de um
executor existir — autenticação, fila, lease, heartbeat, confirmação explícita
e sanitização do estado persistido.
"""
import json
import os
import socket
import shlex
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

from arkher_station_worker import game_dev_recipe

ROOT = os.path.dirname(os.path.abspath(__file__))
TOKEN = 'station-test-token-456'


def porta_livre():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


def req(base, path, method='GET', body=None, token=TOKEN, esperado=None):
    data = None if body is None else json.dumps(body).encode()
    headers = {'Accept': 'application/json'}
    if data is not None:
        headers['Content-Type'] = 'application/json'
    if token:
        headers['Authorization'] = 'Bearer ' + token
    r = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=5) as x:
            out = json.loads(x.read().decode())
            code = x.status
    except urllib.error.HTTPError as e:
        code = e.code
        try:
            out = json.loads(e.read().decode())
        except Exception:
            out = {}
    if esperado is not None and code != esperado:
        raise AssertionError('%s %s: HTTP %s != %s (%s)' % (method, path, code, esperado, out))
    return code, out


def assert_true(cond, msg, extra=''):
    if not cond:
        raise AssertionError(msg + (': ' + extra if extra else ''))
    print('  ok  ' + msg)


def test_recipes():
    godot = game_dev_recipe('godot', '/tmp/meu jogo', {})
    assert_true(godot['ok'] and 'godot --headless' in godot['steps'][0]['cmd'],
                'receita Godot gera teste headless')
    blender = game_dev_recipe('blender', '/tmp/cena', {'action': 'render'})
    assert_true(blender['ok'] and 'blender -b' in blender['steps'][0]['cmd']
                and blender['artifacts'], 'receita Blender gera render e artefato esperado')
    unity = game_dev_recipe('unity', '/tmp/unity', {'action': 'build'})
    assert_true(unity['ok'] and '-batchmode' in unity['steps'][0]['cmd']
                and 'Build.Android' in unity['steps'][0]['cmd'], 'receita Unity gera build em lote')
    unreal = game_dev_recipe('unreal', '/tmp/unreal', {'action': 'build'})
    assert_true(unreal['ok'] and 'BuildCookRun' in unreal['steps'][0]['cmd'],
                'receita Unreal gera BuildCookRun')
    roblox = game_dev_recipe('roblox', '/tmp/roblox', {})
    assert_true(not roblox['ok'] and roblox.get('needsGui'),
                'receita Roblox não finge que Studio roda headless')


def main():
    test_recipes()
    port = porta_livre()
    with tempfile.TemporaryDirectory(prefix='arkher-station-') as state:
        env = dict(os.environ)
        env.update({
            'ARKHER_PORT': str(port),
            'ARKHER_STATE': state,
            'ARKHER_AGENT_TOKEN': TOKEN,
        })
        proc = subprocess.Popen([sys.executable, 'agent.py'], cwd=ROOT, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        base = 'http://127.0.0.1:%d' % port
        try:
            deadline = time.time() + 8
            while time.time() < deadline:
                try:
                    if req(base, '/health')[0] == 200:
                        break
                except Exception:
                    time.sleep(.05)
            else:
                raise AssertionError('agent não subiu: ' + (proc.stdout.read()[-500:] if proc.stdout else ''))

            assert_true(req(base, '/station', token='')[0] == 401, 'Station exige Bearer token')
            _, station = req(base, '/station')
            worker_id = station['worker']['id']
            assert_true(worker_id, 'worker tem identidade estável')

            job_body = {
                'job': {
                    'id': 'build-integration-1',
                    'kind': 'build',
                    'priority': 9,
                    'runId': 'run-integration-1',
                    'workerId': worker_id,
                    'payload': {
                        'motor': 'godot',
                        'objetivo': 'validar cena autorizada',
                        'apiKey': 'não pode persistir',
                    },
                }
            }
            code, queued = req(base, '/station/job', 'POST', job_body)
            assert_true(code == 200 and queued['job']['status'] == 'queued', 'job entrou na fila')
            assert_true('apiKey' not in json.dumps(queued), 'credencial não volta no job')

            _, nxt = req(base, '/station/job/next?workerId=' + urllib.parse.quote(worker_id))
            claimed = nxt['job']
            assert_true(nxt['estado'] == 'claimed' and claimed['id'] == 'build-integration-1', 'worker reivindicou o job')
            assert_true(claimed.get('leaseToken'), 'claim devolve lease efêmero')
            lease = claimed['leaseToken']

            _, beat = req(base, '/station/job/heartbeat', 'POST', {
                'jobId': claimed['id'], 'leaseToken': lease, 'progress': .5,
                'metrics': {'tests': 2}, 'message': 'compilação observada',
            })
            assert_true(beat['job']['status'] == 'running' and beat['job']['progress'] == .5,
                        'heartbeat renova lease e registra progresso')

            _, done = req(base, '/station/job/complete', 'POST', {
                'jobId': claimed['id'], 'leaseToken': lease, 'status': 'completed',
                'result': {'code': 0, 'verified': True, 'metrics': {'tests': 3}},
            })
            assert_true(done['job']['status'] == 'completed' and done['job']['verified'] is True,
                        'worker confirma conclusão com resultado observado')
            assert_true('leaseToken' not in json.dumps(done), 'lease não aparece depois da conclusão')

            code, again = req(base, '/station/job/complete', 'POST', {
                'jobId': claimed['id'], 'leaseToken': lease, 'status': 'completed', 'result': {},
            })
            assert_true(code == 409 and not again.get('ok'), 'lease antigo não pode confirmar duas vezes')

            # Expiração é reconciliada sem esperar 15 segundos: o teste move
            # o relógio do lease no arquivo efêmero do worker.
            req(base, '/station/job', 'POST', {'job': {
                'id': 'build-requeue-1', 'kind': 'build', 'payload': {'projeto': 'outro'},
            }})
            _, retry = req(base, '/station/job/next?workerId=' + urllib.parse.quote(worker_id))
            retry_file = os.path.join(state, 'station.json')
            with open(retry_file, encoding='utf-8') as f:
                raw = json.load(f)
            for item in raw['jobs']:
                if item.get('id') == retry['job']['id']:
                    item['leaseUntil'] = time.time() - 1
            with open(retry_file, 'w', encoding='utf-8') as f:
                json.dump(raw, f)
            _, listed = req(base, '/station/jobs')
            rec = next(x for x in listed['items'] if x['id'] == 'build-requeue-1')
            assert_true(rec['status'] == 'queued' and rec['attempts'] == 1,
                        'lease expirado volta para queued com tentativa contada')

            _, retry2 = req(base, '/station/job/next?workerId=' + urllib.parse.quote(worker_id))
            with open(retry_file, encoding='utf-8') as f:
                raw = json.load(f)
            for item in raw['jobs']:
                if item.get('id') == retry2['job']['id']:
                    item['leaseUntil'] = time.time() - 1
            with open(retry_file, 'w', encoding='utf-8') as f:
                json.dump(raw, f)
            req(base, '/station/jobs')
            _, retry3 = req(base, '/station/job/next?workerId=' + urllib.parse.quote(worker_id))
            with open(retry_file, encoding='utf-8') as f:
                raw = json.load(f)
            for item in raw['jobs']:
                if item.get('id') == retry3['job']['id']:
                    item['leaseUntil'] = time.time() - 1
            with open(retry_file, 'w', encoding='utf-8') as f:
                json.dump(raw, f)
            _, listed_final = req(base, '/station/jobs')
            final = next(x for x in listed_final['items'] if x['id'] == 'build-requeue-1')
            assert_true(final['status'] == 'failed' and final['attempts'] == 3,
                        'terceira expiração falha sem declarar execução')

            command = '%s -c %s' % (
                shlex.quote(sys.executable), shlex.quote("print('station-runner-ok')"))
            req(base, '/station/job', 'POST', {'job': {
                'id': 'command-runner-1', 'kind': 'command',
                'payload': {'cmd': command, 'timeout': 30},
            }})
            runner = subprocess.run([
                sys.executable, 'arkher_station_worker.py', '--agent', base,
                '--token', TOKEN, '--allow-command', '--once',
            ], cwd=ROOT, capture_output=True, text=True, timeout=20)
            assert_true(runner.returncode == 0, 'executor opt-in rodou um command job real', runner.stdout[-300:])
            _, after_runner = req(base, '/station/jobs')
            executed = next(x for x in after_runner['items'] if x['id'] == 'command-runner-1')
            assert_true(executed['status'] == 'completed' and executed['result']['verified'] is True,
                        'resultado do executor registra código observado e verified=true')

            project = os.path.join(state, 'game-project')
            os.makedirs(project, exist_ok=True)
            with open(os.path.join(project, 'build.txt'), 'w', encoding='utf-8') as f:
                f.write('artefato game-dev observado\\n')
            game_command = '%s -c %s' % (
                shlex.quote(sys.executable), shlex.quote("print('game-dev-step-ok')"))
            req(base, '/station/job', 'POST', {'job': {
                'id': 'game-dev-artifact-1', 'kind': 'game-dev',
                'payload': {
                    'motor': 'godot', 'project': project,
                    'steps': [{'name': 'headless-test', 'cmd': game_command}],
                    'artifacts': ['build.txt'],
                },
            }})
            runner_env = dict(os.environ, ARKHER_STATE=state, ARKHER_AGENT_TOKEN=TOKEN)
            game_runner = subprocess.run([
                sys.executable, 'arkher_station_worker.py', '--agent', base,
                '--token', TOKEN, '--allow-game-dev', '--kinds', 'game-dev', '--once',
            ], cwd=ROOT, env=runner_env, capture_output=True, text=True, timeout=20)
            assert_true(game_runner.returncode == 0, 'handler game-dev executou o passo real', game_runner.stdout[-300:])
            _, after_game = req(base, '/station/jobs')
            game = next(x for x in after_game['items'] if x['id'] == 'game-dev-artifact-1')
            artifact = game['result']['artifacts'][0]
            assert_true(game['status'] == 'completed' and game['result']['verified'] is True,
                        'game-dev só conclui depois do processo e do artefato')
            assert_true(artifact['copied'] and len(artifact['sha256']) == 64,
                        'artefato foi copiado com sha256')
            assert_true(os.path.isfile(os.path.join(state, 'work', artifact['path'])),
                        'artefato ficou no workspace servível pelo agent')

            _, public = req(base, '/station')
            text = json.dumps(public, ensure_ascii=False)
            assert_true('apiKey' not in text and 'não pode persistir' not in text,
                        'estado persistido não contém segredo nem prompt sensível')
            assert_true(public['jobs'][0]['status'] == 'completed', 'estado do worker reconcilia como completed')
            assert_true(any(x.get('type') == 'station_job_complete' for x in public['events']),
                        'conclusão vira evento auditável')
            print('✅ STATION WORKER OK — fila autenticada, lease, heartbeat e confirmação passaram')
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('❌ STATION WORKER FALHOU:', exc)
        sys.exit(1)
