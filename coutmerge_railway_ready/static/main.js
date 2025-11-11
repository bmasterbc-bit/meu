const fileinput = document.getElementById('fileinput');
const btnUpload = document.getElementById('btnUpload');
const status = document.getElementById('status');
const log = document.getElementById('log');
const progress = document.getElementById('progress');
const linksDiv = document.getElementById('links');
const mergedLink = document.getElementById('merged');
const txtLink = document.getElementById('txt');
const csvLink = document.getElementById('csv');
const pdfLink = document.getElementById('pdf');
const zipLink = document.getElementById('zip');

function appendLog(text){
  log.innerText += '\n' + text;
  log.scrollTop = log.scrollHeight;
}

btnUpload.addEventListener('click', async ()=>{
  if(!fileinput.files.length){ alert('Escolha ao menos um arquivo.'); return; }
  const form = new FormData();
  for(const f of fileinput.files) form.append('files', f);
  status.innerText = 'Enviando arquivos...';
  appendLog('Enviando ' + fileinput.files.length + ' arquivos');

  const resp = await fetch('/upload', { method:'POST', body: form });
  if(!resp.ok){ appendLog('Erro no upload'); status.innerText = 'Erro'; return; }
  const data = await resp.json();
  appendLog('Processamento concluído. Links prontos.');
  mergedLink.href = data.merged_url;
  txtLink.href = data.log_txt;
  csvLink.href = data.log_csv;
  pdfLink.href = data.log_pdf;
  zipLink.href = data.zip;
  linksDiv.style.display = 'block';
  status.innerText = 'Concluído. Baixe os arquivos abaixo.';
  progress.value = 1;
});
