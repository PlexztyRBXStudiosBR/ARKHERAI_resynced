# Execução Linux com restart e limites

Os arquivos desta pasta são templates; eles não instalam engine nem criam um
segredo. O serviço não deve ser usado sem uma revisão das raízes e dos limites
da máquina autorizada.

## Instalação mínima

```bash
sudo useradd --system --home /var/lib/arkher --shell /usr/sbin/nologin arkher
sudo install -d -o arkher -g arkher /opt/arkher /var/lib/arkher/work /etc/arkher
sudo cp -a . /opt/arkher/
sudo cp deploy/arkher.env.example /etc/arkher/agent.env
sudo editor /etc/arkher/agent.env                 # token aleatório >= 20 chars
sudo chmod 600 /etc/arkher/agent.env
sudo cp deploy/arkher-agent.service /etc/systemd/system/
sudo cp deploy/arkher-station-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
set -a; . /etc/arkher/agent.env; set +a
sudo --preserve-env=ARKHER_AGENT_TOKEN,ARKHER_STATE,ARKHER_REQUIRE_TOKEN \
  -u arkher python3 /opt/arkher/arkher_doctor.py --json --state /var/lib/arkher
sudo systemctl enable --now arkher-agent.service
sudo systemctl enable --now arkher-station-worker.service
curl -fsS http://127.0.0.1:8765/ready
```

O `source` acima pressupõe que o arquivo de ambiente contém valores shell-safe;
para tokens com caracteres especiais, use um mecanismo de secrets que exporte a
variável sem interpretá-la. Em produção, mantenha o arquivo com permissão 600.
O token só é passado por ambiente e não aparece no `ExecStart` nem no `ps` do
worker.

O `arkher-agent.service` reinicia o HTTP agent após falha, limita memória/tarefas
via cgroups e grava somente em `/var/lib/arkher`. O worker também reinicia, usa
`--workspace` e só habilita `game-dev`; `command` continua desabilitado até o
operador adicionar deliberadamente `--allow-command` após revisar a máquina.
Leases e estado são persistidos pelo agente; um processo interrompido não vira
sucesso depois do restart.

## Engines e GUI

`systemd` prova supervisão do processo, não prova Blender/Godot/Unity/Unreal ou
Roblox. Rode `arkher_doctor.py --engines ... --require-engines` e depois um
job de projeto autorizado. Roblox Studio ainda exige sessão gráfica/login; GPU,
render, build, playtest e qualidade visual só são aceitos após observação real.
