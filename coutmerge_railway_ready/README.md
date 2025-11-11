# CoutMerge Web (Railway-ready)

## O que está aqui
- Aplicação FastAPI que recebe múltiplos arquivos, agrupa por sufixo `_PD` quando presente e mescla PDFs/imagens.
- Gera logs nos formatos TXT, CSV e PDF e disponibiliza ZIP com todos os resultados.
- Pronto para deploy em Railway (Procfile incluído) ou via Docker.

## Deploy rápido (Railway)
1. Crie uma conta em https://railway.app (Google/GitHub/email).
2. Crie um novo projeto e conecte um repositório Git contendo estes arquivos, ou copie os arquivos para um repositório e importe.
3. Railway detectará a aplicação Python e usará `Procfile`.
4. Após deploy, abra o link público e use a interface.

## Rodando localmente com Docker
```bash
docker build -t coutmerge .
docker run -p 8000:8000 -v $(pwd)/tmp_jobs:/app/tmp_jobs coutmerge
```

## Rodando local sem Docker
```bash
python -m venv .venv
source .venv/bin/activate  # ou .venv\Scripts\activate no Windows
pip install -r requirements.txt
uvicorn main:app --reload
```

## Observações
- A compressão disponível é simples; para compressões avançadas, instale e use Ghostscript.
- Mantenha rotina de limpeza da pasta `tmp_jobs` se vai processar muitos arquivos.
