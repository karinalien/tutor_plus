// timetable.js — динамическое расписание + журнал уроков

let currentDate = new Date();
const DOW = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'];
const RU_DOW = ['Понедельник','Вторник','Среда','Четверг','Пятница','Суббота','Воскресенье'];

const STORAGE_KEY = 'tutor_lessons_history_v1';

// ---------- утилиты ----------

function pad(n){ return n.toString().padStart(2,'0'); }

function fmtDateTitle(d){
  const dd = pad(d.getDate());
  const month = d.toLocaleDateString('ru-RU',{month:'long'});
  const year  = d.getFullYear();
  const dow   = RU_DOW[(d.getDay()+6)%7].toLowerCase();
  return `${dow}, ${dd} ${month} ${year} г.`;
}

function toDowName(d){
  const js = d.getDay();
  return DOW[(js + 6) % 7];
}

function isoDate(d){
  const y = d.getFullYear();
  const m = pad(d.getMonth()+1);
  const day = pad(d.getDate());
  return `${y}-${m}-${day}`;
}

// ---------- работа с localStorage ----------

function loadLessonsFromStorage(){
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    console.warn('Ошибка чтения localStorage', e);
    return [];
  }
}

function saveLessonsToStorage(list){
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  } catch (e) {
    console.warn('Ошибка записи localStorage', e);
  }
}

// ---------- расписание на день ----------

async function loadScheduleForCurrentDay(){
  // заголовок с датой
  const titleEl = document.getElementById('currentPeriod');
  if (titleEl) titleEl.textContent = fmtDateTitle(currentDate);

  // таблица
  const body = document.getElementById('schedule-body');
  if (!body) return;
  body.innerHTML = `<tr><td colspan="3" style="padding:16px;">Загрузка…</td></tr>`;

  try {
    const res = await fetch('/api/schedule', {credentials:'same-origin'});
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const all = data.schedule || [];

    const dow = toDowName(currentDate);
    const items = all
      .filter(s => (s.day_of_week || '').toLowerCase() === dow)
      .sort((a,b) => (a.start_time > b.start_time ? 1 : -1));

    if (items.length === 0) {
      body.innerHTML = `<tr><td colspan="3" style="padding:16px;">Нет занятий на выбранный день</td></tr>`;
      return;
    }

    const dateStr = isoDate(currentDate);

    body.innerHTML = items.map(s => {
      const time = `${(s.start_time||'').slice(0,5)} — ${(s.end_time||'').slice(0,5)}`;
      const fullName = [s.student_name, s.student_last_name].filter(Boolean).join(' ') || 'Ученик';
      const topic = s.topic_title || 'Занятие';
      const examType = (s.exam_type || '').toUpperCase();
      const examClass = (s.exam_type || '').toLowerCase();
      const initials = fullName.split(' ').map(w => w[0]||'').join('').slice(0,2).toUpperCase();
      const price = s.lesson_price || 0;

      return `
        <tr class="schedule-row">
          <td class="time-slot">${time}</td>
          <td>
            <div class="lesson-card ${examClass}">
              <div class="lesson-header">
                <div class="student-info">
                  <div class="student-avatar">${initials}</div>
                  <div class="student-details">
                    <h4>${fullName}</h4>
                    <p>${examType}</p>
                  </div>
                </div>
                <span class="lesson-type ${examClass}">${examType}</span>
              </div>
              <div class="lesson-details">
                <div class="lesson-topic">${topic}</div>
              </div>
              <div class="lesson-actions">
                <button
                  class="btn-small btn-start lesson-state-btn"
                  data-schedule-id="${s.id}"
                  data-student="${fullName}"
                  data-exam="${examType}"
                  data-price="${price}"
                  data-time="${time}"
                >Начать</button>
                <button class="btn-small btn-edit">✏️</button>
              </div>
            </div>
          </td>
          <td class="actions-col"></td>
        </tr>
      `;
    }).join('');

    attachLessonButtons(dateStr);

  } catch (e) {
    console.error('Ошибка загрузки расписания:', e);
    body.innerHTML = `<tr><td colspan="3" style="padding:16px;">Не удалось загрузить расписание</td></tr>`;
  }
}

// ---------- логика кнопок Начать / Завершить / Проведен ----------

function attachLessonButtons(dateStr){
  const lessons = loadLessonsFromStorage();
  document.querySelectorAll('.lesson-state-btn').forEach(btn => {
    const scheduleId = btn.dataset.scheduleId;
    const key = `${dateStr}-${scheduleId}`;
    const record = lessons.find(l => l.key === key);

    // если урок уже проведен — сразу показываем "Проведен"
    if (record) {
      setButtonDone(btn);
    } else {
      btn.dataset.state = 'idle';
      btn.onclick = onLessonButtonClick; // перезаписываем хендлер, чтобы не плодить слушатели
    }
  });
}

function onLessonButtonClick(e){
  const btn = e.currentTarget;
  const state = btn.dataset.state || 'idle';

  if (state === 'idle') {
    // Начать → Завершить
    btn.dataset.state = 'running';
    btn.textContent = 'Завершить';
    btn.classList.remove('btn-start');
    btn.classList.add('btn-finish');
    return;
  }

  if (state === 'running') {
    // Завершить → Проведен + запись в журнал
    btn.dataset.state = 'done';
    setButtonDone(btn);
    saveFinishedLessonFromButton(btn);
  }
}

function setButtonDone(btn){
  btn.textContent = 'Проведен';
  btn.classList.remove('btn-start','btn-finish');
  btn.classList.add('btn-done');
  btn.disabled = true;
}

function saveFinishedLessonFromButton(btn) {
    const dateStr    = isoDate(currentDate);
    const scheduleId = btn.dataset.scheduleId;
    const key        = `${dateStr}-${scheduleId}`;

    // ---- localStorage ----
    const lessons = loadLessonsFromStorage();
    if (lessons.some(l => l.key === key)) {
        return; // уже записано в хранилище
    }

    const lessonObj = {
        key,
        date: dateStr,
        schedule_id: Number(scheduleId),
        student: btn.dataset.student || "",
        exam: btn.dataset.exam || "",
        price: Number(btn.dataset.price || 0),
        time: btn.dataset.time || "",
        status: "pending"
    };

    lessons.push(lessonObj);
    saveLessonsToStorage(lessons);

    // ---- отправка в БД ----
    fetch("/api/income-lessons", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            date: lessonObj.date,
            student: lessonObj.student,
            exam: lessonObj.exam,
            price: lessonObj.price,
            status: "pending"
        })
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                console.log("💾 Урок добавлен в БД:", data.lesson_id);
            } else {
                console.error("❌ Ошибка записи в БД:", data.message);
            }
        })
        .catch(err => {
            console.error("❌ Ошибка сети:", err);
        });
}



// ---------- навигация по дням ----------

window.previousDay = function(){
  currentDate.setDate(currentDate.getDate() - 1);
  loadScheduleForCurrentDay();
}
window.nextDay = function(){
  currentDate.setDate(currentDate.getDate() + 1);
  loadScheduleForCurrentDay();
}

// ---------- старт страницы ----------

document.addEventListener('DOMContentLoaded', () => {
  fetch('/api/check-auth')
    .then(r => r.json())
    .then(j => j.authenticated ? loadScheduleForCurrentDay()
                                : window.location.assign('/cabinet'))
    .catch(() => loadScheduleForCurrentDay());
});
