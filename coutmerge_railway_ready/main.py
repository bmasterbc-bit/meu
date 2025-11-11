\
    import os
    import uuid
    import zipfile
    import traceback
    import time
    from pathlib import Path
    from fastapi import FastAPI, UploadFile, File, Request
    from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    from PIL import Image
    from PyPDF2 import PdfMerger, PdfReader, PdfWriter
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    import csv
    import hashlib
    import datetime

    app = FastAPI()
    BASE_DIR = Path(__file__).parent
    TMP_DIR = BASE_DIR / "tmp_jobs"
    TMP_DIR.mkdir(exist_ok=True)

    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
    templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

    def nome_base(arquivo_name: str):
        nome, _ = os.path.splitext(arquivo_name)
        partes = nome.split("_PD")
        return partes[0] if len(partes) > 1 else None

    def salvar_imagem_comprimida(img: Image.Image, caminho_destino: Path, limite_kb: int = 800):
        qualidade = 70
        min_qualidade = 20
        caminho_pdf = caminho_destino
        while qualidade >= min_qualidade:
            img.save(caminho_pdf, "PDF", quality=qualidade)
            tamanho_kb = caminho_pdf.stat().st_size / 1024
            if tamanho_kb <= limite_kb:
                return True
            qualidade -= 10
        return False

    def comprimir_pdf_simples(caminho_pdf: Path, limite_kb: int = 800):
        try:
            reader = PdfReader(str(caminho_pdf))
            writer = PdfWriter()
            for p in reader.pages:
                writer.add_page(p)
            temp_path = caminho_pdf.with_name(caminho_pdf.stem + "_comp.pdf")
            with open(temp_path, "wb") as f:
                writer.write(f)
            if temp_path.stat().st_size / 1024 <= limite_kb:
                temp_path.replace(caminho_pdf)
                return True
            else:
                temp_path.unlink()
                return False
        except Exception:
            return False

    def gerar_log_files(job_dir: Path, log_entries: list, merged_path: Path, user_ip: str):
        \"\"\"Gera log.txt, log.csv e log.pdf dentro job_dir/logs\"\"\"\n        logs_dir = job_dir / "logs"
        logs_dir.mkdir(exist_ok=True)
        # TXT
        txt_path = logs_dir / "log.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"Operação: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\\n")
            f.write(f"IP aproximado: {user_ip}\\n")
            f.write("\\nArquivos enviados:\\n")
            for e in log_entries:
                f.write(f" - {e['name']} | {e['size_kb']:.1f} KB | status: {e.get('status','')}" + "\\n")
            f.write("\\nArquivo final: " + merged_path.name + "\\n")
            f.write(f"Tamanho final: {merged_path.stat().st_size/1024:.1f} KB\\n")
            # md5
            md5 = hashlib.md5(merged_path.read_bytes()).hexdigest()
            f.write(f\"MD5: {md5}\\n\")
        # CSV
        csv_path = logs_dir / "log.csv"
        with open(csv_path, "w", newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['name','size_kb','status'])
            for e in log_entries:
                writer.writerow([e['name'], f\"{e['size_kb']:.1f}\", e.get('status','')])
            writer.writerow([])
            writer.writerow(['final_file', merged_path.name])
            writer.writerow(['final_size_kb', f\"{merged_path.stat().st_size/1024:.1f}\"])
            writer.writerow(['md5', hashlib.md5(merged_path.read_bytes()).hexdigest()])
            writer.writerow(['timestamp_utc', datetime.datetime.utcnow().isoformat()])
            writer.writerow(['ip', user_ip])
        # PDF (simple)
        pdf_path = logs_dir / "log.pdf"
        c = canvas.Canvas(str(pdf_path), pagesize=A4)
        w, h = A4
        x = 40
        y = h - 40
        c.setFont('Helvetica-Bold', 12)
        c.drawString(x, y, "Relatório de Merge - CoutMerge Web")
        c.setFont('Helvetica', 10)
        y -= 20
        c.drawString(x, y, f\"Operação: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\")
        y -= 15
        c.drawString(x, y, f\"IP aproximado: {user_ip}\")
        y -= 20
        c.drawString(x, y, \"Arquivos enviados:\")
        y -= 15
        for e in log_entries:
            linha = f\" - {e['name']} | {e['size_kb']:.1f} KB | {e.get('status','')}\"
            if y < 80:
                c.showPage()
                y = h - 40
            c.drawString(x, y, linha)
            y -= 12
        if y < 120:
            c.showPage()
            y = h - 40
        c.drawString(x, y, f\"Arquivo final: {merged_path.name}\")
        y -= 12
        c.drawString(x, y, f\"Tamanho final: {merged_path.stat().st_size/1024:.1f} KB\")
        y -= 12
        c.drawString(x, y, f\"MD5: {hashlib.md5(merged_path.read_bytes()).hexdigest()}\")
        c.save()
        return {'txt': str(txt_path), 'csv': str(csv_path), 'pdf': str(pdf_path)}

    @app.get('/', response_class=HTMLResponse)
    async def index(request: Request):
        return templates.TemplateResponse('index.html', {'request': request})

    @app.post('/upload')
    async def upload(files: list[UploadFile] = File(...), request: Request = None):
        \"\"\"Recebe arquivos, processa (merge) e retorna links para download do PDF e logs.\"\"\"\n        job_id = str(uuid.uuid4())
        job_dir = TMP_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        out_dir = job_dir / 'out'
        out_dir.mkdir(exist_ok=True)

        # save uploaded files
        saved = []
        for file in files:
            dest = job_dir / file.filename
            content = await file.read()
            with open(dest, 'wb') as f:
                f.write(content)
            saved.append(dest)
        # build groups by nome_base; if none found, merge all in upload order
        grupos = {}
        for p in saved:
            base = nome_base(p.name)
            if base:
                grupos.setdefault(base, []).append(p)
        if not grupos:
            # single group: all files in order uploaded
            grupos = {'ALL': saved}

        log_entries = []
        merger = PdfMerger()
        merged_name = f\"merge_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf\"
        merged_path = out_dir / merged_name

        try:
            for base in sorted(grupos.keys()):
                arquivos = grupos[base]
                # sort by filename to keep deterministic order
                arquivos = sorted(arquivos, key=lambda p: p.name)
                for p in arquivos:
                    size_kb = p.stat().st_size / 1024
                    try:
                        if p.suffix.lower() == '.pdf':
                            merger.append(str(p))
                            status = 'appended_pdf'
                        else:
                            img = Image.open(str(p)).convert('RGB')
                            temp_pdf = job_dir / (p.name + '.tmp.pdf')
                            sucesso = salvar_imagem_comprimida(img, temp_pdf)
                            merger.append(str(temp_pdf))
                            temp_pdf.unlink(missing_ok=True)
                            status = 'appended_image'
                    except Exception as e:
                        status = f'erro:{e}'
                    log_entries.append({'name': p.name, 'size_kb': size_kb, 'status': status})
            merger.write(str(merged_path))
            merger.close()
        except Exception as e:
            traceback.print_exc()
            return JSONResponse({'error': 'Erro durante o merge', 'detail': str(e)}, status_code=500)

        # try simple compression if bigger than 800KB
        try:
            if merged_path.stat().st_size / 1024 > 800:
                comprimir_pdf_simples(merged_path)
        except:
            pass

        # ip approx
        user_ip = None
        try:
            client_host = request.client.host if request and request.client else None
            user_ip = client_host or 'unknown'
        except:
            user_ip = 'unknown'

        # generate logs
        logs = gerar_log_files(job_dir, log_entries, merged_path, user_ip)

        # zip outputs (merged + logs)
        zip_path = job_dir / 'resultados.zip'
        with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(merged_path, arcname=merged_path.name)
            zf.write(logs['txt'], arcname='log.txt')
            zf.write(logs['csv'], arcname='log.csv')
            zf.write(logs['pdf'], arcname='log.pdf')

        return {\n            'job_id': job_id,\n            'merged_url': f'/download/{job_id}/merged.pdf',\n            'log_txt': f'/download/{job_id}/log.txt',\n            'log_csv': f'/download/{job_id}/log.csv',\n            'log_pdf': f'/download/{job_id}/log.pdf',\n            'zip': f'/download/{job_id}/resultados.zip'\n        }\n    
    @app.get('/download/{job_id}/{fname}')
    def download_file(job_id: str, fname: str):
        job_dir = TMP_DIR / job_id\n        mapping = {\n            'merged.pdf': job_dir / 'out' / next((job_dir / 'out').iterdir()).name if job_dir.exists() and (job_dir / 'out').exists() and any((job_dir / 'out').iterdir()) else None\n        }\n        # simplified mapping: check files by name
        candidates = list(job_dir.rglob(fname)) if job_dir.exists() else []\n        if candidates:\n            return FileResponse(str(candidates[0]), filename=fname)\n        return {'error': 'Arquivo não encontrado'}\n    