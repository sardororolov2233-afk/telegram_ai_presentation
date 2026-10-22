'use strict';
const $ = id => document.getElementById(id);
const tg = window.Telegram?.WebApp;
let token = '', account = null, tab = 'presentations', catalog = [], busy = false;
let currentJob = null, requestSeed = null, requestFingerprint = null, userId = null;

function flash(message, error = false) {
  $('flash').textContent = message;
  $('flash').classList.remove('hidden');
  $('flash').classList.toggle('error', error);
}

async function api(path, options = {}) {
  const headers = {...(options.headers || {})};
  if (token) headers.Authorization = 'Bearer ' + token;
  const response = await fetch('/api/v1' + path, {...options, headers});
  if (!response.ok) {
    let body;
    try { body = await response.json(); } catch {}
    throw new Error(typeof body?.detail === 'string' ? body.detail : 'So‘rov bajarilmadi. Qayta urinib ko‘ring.');
  }
  return response.json();
}

function setTab(next) {
  tab = next;
  for (const button of document.querySelectorAll('[data-tab]')) {
    button.setAttribute('aria-selected', String(button.dataset.tab === next));
  }
  const design = next === 'designs', article = next === 'articles';
  $('create-panel').classList.toggle('hidden', next === 'account');
  $('account-panel').classList.toggle('hidden', next !== 'account');
  $('template-fields').hidden = design || article;
  $('format-field').hidden = design || article;
  $('author-field').hidden = design;
  $('author').required = !design;
  $('references-field').hidden = design;
  $('academic-note').hidden = design;
  $('design-fields').hidden = !design;
  $('subject').required = !design && !article;
  $('form-title').textContent = design ? 'Dizayn yaratamiz' : article ? 'Ilmiy maqola tayyorlash' : 'Taqdimotni boshlaymiz';
  $('topic-label').textContent = design ? 'Dizayn tavsifi va undagi yozuvlar' : 'Mavzu';
  $('product-badge').textContent = design ? '3 ta dizayn varianti' : article ? 'Bepul · Word hujjati' : 'Tayyor fan shablonlari';
  refreshQuote();
  updateBadge();
}

function refreshQuote() {
  const service = tab === 'articles' ? 'article' : tab === 'designs' ? 'design' : 'presentation';
  const offer = account?.quotes?.[service];
  $('quote').textContent = offer ? offer.required_credits ? `${offer.required_credits} kvota` : 'Bepul' : '—';
  $('create').disabled = !offer?.allowed || busy;
  $('create').textContent = busy ? 'Ishingiz tayyorlanmoqda...' : tab === 'articles' ? 'Maqola yaratish' : tab === 'designs' ? 'Dizayn yaratish' : 'Taqdimot yaratish';
  $('access-note').textContent = offer?.allowed
    ? offer.required_credits ? 'Yaratish yakunlanmasa band qilingan kvota qaytariladi.' : 'Bu xizmat kvota sarflamaydi.'
    : 'Yangi do‘st taklif qilib 1 kvota oling.';
}

async function loadAccount() {
  account = await api('/commerce');
  $('balance').textContent = `${account.referral_credits} kvota`;
  $('credit-count').textContent = account.referral_credits;
  $('friend-count').textContent = account.confirmed_referrals;
  $('course-count').textContent = account.course_credits;
  $('ref-progress').textContent = `${account.confirmed_referrals} ta tasdiqlangan do‘st. Har bir yangi do‘st uchun +1 kvota.`;
  $('referral-link').textContent = account.referral_link;
  $('policy').textContent = account.policy;
  refreshQuote();
}

function updateVariants() {
  const subject = catalog.find(item => item.subject === $('subject').value);
  $('variant').replaceChildren();
  for (const variant of subject?.variants || []) {
    const option = document.createElement('option');
    option.value = variant.variant;
    option.textContent = `${variant.variant}-variant · ${variant.slide_count} slayd`;
    $('variant').append(option);
  }
  updateBadge();
}

function updateBadge() {
  if (tab !== 'presentations') return;
  const item = catalog.find(item => item.subject === $('subject').value)?.variants.find(item => String(item.variant) === $('variant').value);
  if (item) $('product-badge').textContent = `${item.slide_count} slayd · ${item.plan_count} ta reja · ko‘pi bilan 3 ta yangi rasm`;
}

function shareReferral() {
  if (!account) return;
  const link = 'https://t.me/share/url?url=' + encodeURIComponent(account.referral_link) + '&text=' + encodeURIComponent('Orzu bilan taqdimot, referat va kurs ishini tayyorlang.');
  if (tg?.openTelegramLink) tg.openTelegramLink(link);
  else window.open(link, '_blank', 'noopener');
}

async function pollJob(id) {
  currentJob = id;
  $('order-status').classList.remove('hidden');
  $('download').classList.add('hidden');
  for (let attempt = 0; attempt < 400; attempt++) {
    const job = await api('/jobs/' + id);
    if (job.status === 'completed' || job.status === 'failed') {
      const completed = job.status === 'completed';
      $('order-title').textContent = completed ? 'Faylingiz tayyor' : 'Buyurtma yakunlanmadi';
      $('order-description').textContent = completed
        ? job.telegram_sent ? 'Telegramga yuborildi. Shu yerdan ham yuklab olishingiz mumkin.' : 'Faylni quyidagi tugma orqali yuklab oling.'
        : job.message;
      $('download').classList.toggle('hidden', !completed);
      localStorage.removeItem('orzu:job:' + userId);
      await loadAccount();
      return;
    }
    $('order-title').textContent = job.status === 'queued' ? 'Buyurtma navbatda' : 'Ishingiz tayyorlanmoqda';
    $('order-description').textContent = 'Mini ilovani yopsangiz ham buyurtma saqlanadi. Qayta ochib natijani tekshirishingiz mumkin.';
    await new Promise(resolve => setTimeout(resolve, 3000));
  }
  flash('Buyurtma davom etmoqda. Natijani mini ilovani qayta ochib tekshiring.');
}

function showDesigns(images) {
  $('design-images').replaceChildren();
  for (const [index, url] of images.entries()) {
    if (!url.startsWith('data:image/png;base64,')) continue;
    const image = document.createElement('img');
    image.src = url;
    image.alt = `Dizaynning ${index + 1}-varianti`;
    image.style.cssText = 'width:100%;height:auto;border-radius:12px;margin-top:12px';
    const download = document.createElement('a');
    download.className = 'secondary';
    download.href = url;
    download.download = `orzu-dizayn-${index + 1}.png`;
    download.textContent = `${index + 1}-variantni yuklab olish`;
    $('design-images').append(image, download);
  }
  $('design-result').classList.remove('hidden');
  $('design-result').scrollIntoView({behavior: 'smooth'});
}

$('generator').addEventListener('submit', async event => {
  event.preventDefault();
  if (busy || !account) return;
  const design = tab === 'designs', article = tab === 'articles';
  const form = new FormData();
  form.set('topic', $('topic').value.trim());
  form.set('author', $('author').value.trim());
  form.set('language', $('language').value);
  form.set('send_to_telegram', 'true');
  form.set(article ? 'references' : 'bibliography_text', $('references').value);
  if (!article && !design) {
    form.set('subject', $('subject').value);
    form.set('variant', $('variant').value);
    form.set('document_format', $('document_format').value);
    const files = Array.from($('images').files);
    if (files.length > 3 || files.some(file => file.size > 5 * 1024 * 1024)) return flash('Ko‘pi bilan 3 ta rasm, har biri 5 MB gacha.', true);
    for (const file of files) form.append('images', file);
  }
  const designBody = {description: $('topic').value.trim(), format: $('design-format').value,
    style: $('design-style').value, lang: $('language').value, send_to_telegram: true};
  const fingerprint = JSON.stringify(design ? designBody : [tab, ...Array.from(form.entries()).map(([key, value]) => [key, value instanceof File ? `${value.name}:${value.size}:${value.lastModified}` : value])]);
  if (fingerprint !== requestFingerprint) {
    requestSeed = crypto.randomUUID();
    requestFingerprint = fingerprint;
  }
  busy = true;
  refreshQuote();
  $('flash').classList.add('hidden');
  try {
    if (design) {
      const result = await api('/designs/generate', {method: 'POST', headers: {'Content-Type': 'application/json', 'Idempotency-Key': requestSeed}, body: JSON.stringify(designBody)});
      showDesigns(result.images);
      await loadAccount();
    } else {
      const order = await api(article ? '/articles/generate' : '/presentations/generate', {method: 'POST', headers: {'Idempotency-Key': requestSeed}, body: form});
      localStorage.setItem('orzu:job:' + userId, order.id);
      await loadAccount();
      await pollJob(order.id);
    }
    requestFingerprint = null;
    requestSeed = null;
  } catch (error) {
    flash(error.message, true);
    await loadAccount().catch(() => {});
  } finally {
    busy = false;
    refreshQuote();
  }
});

$('download').addEventListener('click', async () => {
  try {
    const response = await fetch('/api/v1/jobs/' + currentJob + '/download', {headers: {Authorization: 'Bearer ' + token}});
    if (!response.ok) throw new Error('Faylni olishda xatolik yuz berdi.');
    const url = URL.createObjectURL(await response.blob());
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = (response.headers.get('Content-Disposition')?.match(/filename="?([^";]+)"?/) || [])[1] || 'natija';
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  } catch (error) { flash(error.message, true); }
});

for (const button of document.querySelectorAll('[data-tab]')) button.addEventListener('click', () => setTab(button.dataset.tab));
$('subject').addEventListener('change', updateVariants);
$('variant').addEventListener('change', updateBadge);
$('invite').addEventListener('click', () => {setTab('account'); $('account-panel').scrollIntoView({behavior: 'smooth'});});
$('share-referral').addEventListener('click', shareReferral);

(async () => {
  tg?.ready();
  tg?.expand();
  const requested = new URLSearchParams(location.search).get('tab');
  setTab(['articles', 'designs', 'account'].includes(requested) ? requested : 'presentations');
  try {
    catalog = (await api('/presentations/templates')).subjects;
    $('subject').replaceChildren();
    for (const item of catalog) {
      const option = document.createElement('option');
      option.value = item.subject;
      option.textContent = item.label;
      $('subject').append(option);
    }
    $('subject').value = 'minimalizm';
    updateVariants();
    if (!tg?.initData) throw new Error('Mini ilovani Telegram botdagi tugma orqali oching.');
    const auth = await api('/auth/telegram', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({init_data: tg.initData})});
    token = auth.access_token;
    userId = auth.user.id;
    $('author').value = auth.user.first_name || '';
    await loadAccount();
    const saved = localStorage.getItem('orzu:job:' + userId);
    if (saved) {
      busy = true;
      refreshQuote();
      try { await pollJob(saved); } finally { busy = false; refreshQuote(); }
    }
  } catch (error) {
    $('auth-error').textContent = error.message;
    $('auth-error').classList.remove('hidden');
  }
})();
