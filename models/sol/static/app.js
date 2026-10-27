'use strict';
const $ = id => document.getElementById(id);
const labels = {queued:'대기', running:'실행 중', completed:'완료', failed:'실패', cancelled:'취소'};
const pending = new Set();
let loading = false;
let actionError = '';
let lastJobsSignature = '';
function node(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
}
async function api(path, data) {
  const response = await fetch(path, data === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
  return result;
}
function showError(message) {
  $('error').textContent = message;
  $('error').hidden = !message;
}
function time(value) { return value ? new Date(value).toLocaleString('ko-KR') : '—'; }
function renderJobs(jobs) {
  const signature = JSON.stringify([jobs, [...pending]]);
  if (signature === lastJobsSignature) return;
  lastJobsSignature = signature;
  const fragment = document.createDocumentFragment();
  $('count').textContent = `${jobs.length}개 작업`;
  if (!jobs.length) fragment.append(node('div','표시할 작업이 없어. 새 작업을 추가해.', 'empty'));
  for (const job of jobs) {
    const card = node('article', undefined, 'job');
    const top = node('div', undefined, 'job-top');
    const title = node('h3', undefined, 'job-title');
    title.append(node('span', `#${job.id}`, 'job-id'), document.createTextNode(job.title));
    top.append(title, node('span', labels[job.status], `badge ${job.status}`));
    const meta = node('div', undefined, 'job-meta');
    meta.append(node('span', `${job.duration_ms.toLocaleString()}ms`), node('span', `${job.attempt}번째 시도`), node('span', `생성 ${time(job.created_at)}`));
    const bottom = node('div', undefined, 'job-bottom');
    bottom.append(node('div', `시작 ${time(job.started_at)} · 종료 ${time(job.ended_at)}`, 'times'));
    const action = ['queued','running'].includes(job.status) ? 'cancel' : ['failed','cancelled'].includes(job.status) ? 'retry' : null;
    if (action) {
      const button = node('button', pending.has(job.id) ? '처리 중…' : action === 'cancel' ? '취소' : '재시도');
      button.disabled = pending.has(job.id);
      button.addEventListener('click', async () => {
        pending.add(job.id); button.disabled = true; button.textContent = '처리 중…';
        try { await api(`/api/jobs/${job.id}/${action}`, {}); actionError = ''; }
        catch (error) { actionError = error.message; }
        finally { pending.delete(job.id); await refresh(); }
      });
      bottom.append(button);
    }
    card.append(top, meta, bottom); fragment.append(card);
  }
  $('jobs').replaceChildren(fragment);
}
async function refresh() {
  if (loading) return;
  loading = true;
  const filter = $('filter').value;
  try {
    const [stats, result] = await Promise.all([api('/api/stats'), api(`/api/jobs${filter ? '?status='+encodeURIComponent(filter) : ''}`)]);
    if ($('filter').value !== filter) return;
    const cards = Object.entries(labels).map(([state, label]) => {
      const card = node('div', undefined, `stat ${state}`);
      card.append(node('span',label), node('strong',String(stats.counts[state]))); return card;
    });
    $('stats').replaceChildren(...cards); renderJobs(result.jobs);
    $('connection').textContent = `연결됨 · 최대 ${stats.max_workers}개 실행`;
    $('connection').className = 'connection';
    $('updated').textContent = `마지막 갱신 ${new Date().toLocaleTimeString('ko-KR')}`;
    showError(actionError);
  } catch (error) {
    $('connection').textContent = '연결 오류'; $('connection').className = 'connection offline';
    showError(error.message);
  } finally { loading = false; }
}
$('create-form').addEventListener('submit', async event => {
  event.preventDefault(); $('submit').disabled = true; $('form-status').textContent = '작업을 저장하는 중…';
  try {
    await api('/api/jobs', {title:$('title').value, duration_ms:Number($('duration').value), fail_first_attempt:$('fail').checked});
    $('title').value = ''; $('form-status').textContent = '작업을 추가했어.'; actionError = '';
  } catch (error) { actionError = error.message; $('form-status').textContent = '작업을 추가하지 못했어.'; }
  finally { $('submit').disabled = false; showError(actionError); await refresh(); }
});
$('filter').addEventListener('change', refresh);
refresh(); setInterval(refresh, 1000);
