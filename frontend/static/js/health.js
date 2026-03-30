/**
 * health.js — Add/Edit health record form logic.
 *   - Pre-fills form when editing an existing record
 *   - Handles CalorieNinjas nutrition lookup per meal
 *   - Auto-calculates sleep hours from sleep/wake times
 *   - Submits via POST (create) or PUT (update)
 */

// Meal nutrition data cache keyed by meal type
const mealNutrition = {};

document.addEventListener('DOMContentLoaded', async () => {
  if (!requireAuth()) return;

  initDateField();
  initSleepAutoCalc();
  initNutritionLookupButtons();

  const editDate = document.getElementById('edit-date')?.value;
  if (editDate) {
    await prefillForm(editDate);
  }

  document.getElementById('health-form')?.addEventListener('submit', handleSubmit);
});

// ── Date field ────────────────────────────────────────────────────────────────

function initDateField() {
  const dateInput = document.getElementById('date');
  if (!dateInput) return;
  dateInput.max = todayISO();

  const editDate = document.getElementById('edit-date')?.value;
  if (editDate) {
    dateInput.value = editDate;
    dateInput.readOnly = true;
  } else {
    dateInput.value = todayISO();
  }
}

// ── Sleep auto-calculation ────────────────────────────────────────────────────

function initSleepAutoCalc() {
  const sleepIn = document.getElementById('sleep_time');
  const wakeIn = document.getElementById('wake_time');
  const hoursIn = document.getElementById('sleep_hours');

  const calc = () => {
    const h = computeSleepHours(sleepIn?.value, wakeIn?.value);
    if (h !== null && hoursIn) hoursIn.value = h;
  };

  sleepIn?.addEventListener('change', calc);
  wakeIn?.addEventListener('change', calc);
}

// ── Nutrition lookup buttons ──────────────────────────────────────────────────

function initNutritionLookupButtons() {
  document.querySelectorAll('.lookup-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const mealType = btn.dataset.meal;
      const foodInput = document.querySelector(`.meal-food[data-meal="${mealType}"]`);
      const resultEl = document.getElementById(`nutrition-${mealType}`);
      const food = foodInput?.value?.trim();

      if (!food) {
        showToast('Enter a food description first.', 'warning');
        return;
      }

      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

      const res = await apiCall('/api/health/nutrition-lookup', 'POST', { query: food });

      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-search me-1"></i>Lookup Calories';

      if (res?.success) {
        const d = res.data;
        mealNutrition[mealType] = d;
        if (resultEl) {
          resultEl.innerHTML = `
            <strong>${d.total_calories} kcal</strong> &nbsp;|&nbsp;
            Protein: ${d.total_protein_g}g &nbsp;|&nbsp;
            Fat: ${d.total_fat_g}g &nbsp;|&nbsp;
            Carbs: ${d.total_carbs_g}g`;
          resultEl.classList.remove('d-none');
        }
      } else {
        showToast(res?.error || 'Nutrition lookup failed.', 'warning');
      }
    });
  });
}

// ── Pre-fill form for edit mode ───────────────────────────────────────────────

async function prefillForm(date) {
  const res = await apiCall(`/api/health/${date}`);
  if (!res?.success) {
    showToast('Could not load existing record.', 'danger');
    return;
  }

  const r = res.data;

  setField('steps', r.steps);
  setField('weight_kg', r.weight_kg);
  setField('heart_rate', r.heart_rate);
  setField('calories_burned', r.calories_burned);
  setField('sleep_time', r.sleep_time);
  setField('wake_time', r.wake_time);
  setField('sleep_hours', r.sleep_hours);

  // Exercise
  if (r.exercise) {
    setField('exercise_type', r.exercise.type);
    setField('exercise_duration', r.exercise.duration_minutes);
    setField('exercise_calories', r.exercise.calories_burned);
  }

  // Meals
  if (Array.isArray(r.meals)) {
    r.meals.forEach(meal => {
      if (!meal?.type) return;
      const t = meal.type.toLowerCase();
      const timeEl = document.querySelector(`.meal-time[data-meal="${t}"]`);
      const foodEl = document.querySelector(`.meal-food[data-meal="${t}"]`);
      if (timeEl) timeEl.value = meal.time || '';
      if (foodEl) foodEl.value = meal.food || '';

      if (meal.nutrition) {
        mealNutrition[t] = meal.nutrition;
        const resultEl = document.getElementById(`nutrition-${t}`);
        if (resultEl) {
          const d = meal.nutrition;
          resultEl.innerHTML = `<strong>${d.total_calories} kcal</strong> | Protein: ${d.total_protein_g}g | Fat: ${d.total_fat_g}g | Carbs: ${d.total_carbs_g}g`;
          resultEl.classList.remove('d-none');
        }
      }
    });
  }

  // Update submit button text
  const submitText = document.getElementById('submit-text');
  if (submitText) submitText.textContent = 'Update Record';
}

// ── Form submission ───────────────────────────────────────────────────────────

async function handleSubmit(e) {
  e.preventDefault();

  const errorEl = document.getElementById('form-error');
  const successEl = document.getElementById('form-success');
  const btn = document.getElementById('submit-btn');
  const spinner = document.getElementById('submit-spinner');

  errorEl.classList.add('d-none');
  successEl.classList.add('d-none');

  const date = document.getElementById('date')?.value;
  if (!date) {
    errorEl.textContent = 'Date is required.';
    errorEl.classList.remove('d-none');
    return;
  }

  const payload = buildPayload(date);

  btn.disabled = true;
  spinner.classList.remove('d-none');

  const editDate = document.getElementById('edit-date')?.value;
  const isEdit = !!editDate;
  const endpoint = isEdit ? `/api/health/${editDate}` : '/api/health';
  const method = isEdit ? 'PUT' : 'POST';

  const res = await apiCall(endpoint, method, payload);

  btn.disabled = false;
  spinner.classList.add('d-none');

  if (res?.success) {
    showToast(`Health record ${isEdit ? 'updated' : 'saved'} successfully!`, 'success');
    successEl.textContent = `Record ${isEdit ? 'updated' : 'saved'}! Redirecting…`;
    successEl.classList.remove('d-none');
    setTimeout(() => { window.location.href = '/history'; }, 1200);
  } else {
    errorEl.textContent = res?.error || 'Failed to save record.';
    errorEl.classList.remove('d-none');
  }
}

// ── Build payload from form ───────────────────────────────────────────────────

function buildPayload(date) {
  const payload = { date };

  const num = (id) => {
    const v = document.getElementById(id)?.value;
    return v !== '' && v != null ? Number(v) : undefined;
  };
  const str = (id) => document.getElementById(id)?.value?.trim() || undefined;

  if (num('steps') !== undefined)          payload.steps = num('steps');
  if (num('weight_kg') !== undefined)      payload.weight_kg = num('weight_kg');
  if (num('heart_rate') !== undefined)     payload.heart_rate = num('heart_rate');
  if (num('calories_burned') !== undefined) payload.calories_burned = num('calories_burned');
  if (str('sleep_time'))                   payload.sleep_time = str('sleep_time');
  if (str('wake_time'))                    payload.wake_time = str('wake_time');
  if (num('sleep_hours') !== undefined)    payload.sleep_hours = num('sleep_hours');

  // Exercise
  const exType = str('exercise_type');
  const exDur = num('exercise_duration');
  const exCal = num('exercise_calories');
  if (exType || exDur) {
    payload.exercise = {
      type: exType || '',
      duration_minutes: exDur || 0,
      calories_burned: exCal || 0,
    };
  }

  // Meals
  const mealTypes = ['breakfast', 'lunch', 'dinner', 'snack'];
  const meals = [];
  mealTypes.forEach(t => {
    const time = document.querySelector(`.meal-time[data-meal="${t}"]`)?.value;
    const food = document.querySelector(`.meal-food[data-meal="${t}"]`)?.value?.trim();
    if (time || food) {
      const meal = { type: t, time: time || '', food: food || '' };
      if (mealNutrition[t]) meal.nutrition = mealNutrition[t];
      meals.push(meal);
    }
  });
  if (meals.length) payload.meals = meals;

  return payload;
}

// ── Utility ───────────────────────────────────────────────────────────────────

function setField(id, value) {
  const el = document.getElementById(id);
  if (el && value != null) el.value = value;
}
