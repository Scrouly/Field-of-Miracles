/**
 * scenario.js — Управление сценарием мероприятия (Task 12).
 *
 * Перетаскивание/перемещение туров, привязка вопросов, барабанов и призов.
 */

(function () {
  'use strict';

  class ScenarioApp {
    constructor() {
      this.eventId = window.CURRENT_EVENT_ID;
      this.rounds = [];
      this.questions = [];
      this.wheels = [];
      this.prizes = [];
      this.isSaving = false;

      this.initElements();
      this.bindEvents();
      if (this.eventId) {
        this.loadScenario(this.eventId);
      }
    }

    initElements() {
      this.eventSelect = document.getElementById('event-select');
      this.roundsList = document.getElementById('rounds-list');
      this.btnAddRound = document.getElementById('btn-add-round');
      this.btnSaveScenario = document.getElementById('btn-save-scenario');
      this.statCount = document.getElementById('stat-rounds-count');
      this.toastEl = document.getElementById('toast');
    }

    showToast(message, isError = false) {
      if (!this.toastEl) return;
      this.toastEl.textContent = message;
      this.toastEl.className = 'toast ' + (isError ? 'error' : 'success');
      setTimeout(() => {
        this.toastEl.className = 'toast hidden';
      }, 3500);
    }

    async loadScenario(eventId) {
      try {
        const resp = await fetch(`/studio/api/events/${eventId}/rounds/`);
        if (!resp.ok) throw new Error('Ошибка загрузки данных сценария');

        const data = await resp.json();
        this.rounds = data.rounds || [];
        this.questions = data.questions || [];
        this.wheels = data.wheels || [];
        this.prizes = data.prizes || [];

        this.renderRounds();
        this.updateStats();
      } catch (err) {
        this.showToast(err.message, true);
      }
    }

    renderRounds() {
      if (!this.roundsList) return;
      this.roundsList.innerHTML = '';

      if (this.rounds.length === 0) {
        this.roundsList.innerHTML = `
          <div class="card" style="text-align: center; color: var(--color-text-dim); padding: 40px;">
            В мероприятии пока нет туров. Нажмите «＋ Добавить тур» выше.
          </div>
        `;
        return;
      }

      this.rounds.forEach((round, idx) => {
        const card = document.createElement('div');
        card.className = `round-card type-${round.type}`;
        card.dataset.id = round.id;
        card.dataset.index = idx;

        // Question options
        let qOptions = '<option value="">(вопрос не выбран)</option>';
        this.questions.forEach(q => {
          const selected = round.question_id === q.id ? 'selected' : '';
          const preview = q.text.length > 40 ? q.text.slice(0, 40) + '…' : q.text;
          qOptions += `<option value="${q.id}" ${selected}>«${escapeHtml(q.word)}» — ${escapeHtml(preview)}</option>`;
        });

        // Wheel options
        let wOptions = '<option value="">(барабан по умолчанию)</option>';
        this.wheels.forEach(w => {
          const selected = round.wheel_id === w.id ? 'selected' : '';
          wOptions += `<option value="${w.id}" ${selected}>${escapeHtml(w.name)} (${w.sector_count} сект.)</option>`;
        });

        // Prize options
        let pOptions = '<option value="">(без приза)</option>';
        this.prizes.forEach(p => {
          const selected = round.prize_id === p.id ? 'selected' : '';
          pOptions += `<option value="${p.id}" ${selected}>${escapeHtml(p.name)} (${p.cost} очков)</option>`;
        });

        card.innerHTML = `
          <div class="round-order-box">
            <span class="round-num">#${idx + 1}</span>
            <div class="cell-order-btns">
              <button class="btn-order btn-move-up" title="Переместить выше" ${idx === 0 ? 'disabled' : ''}>▲</button>
              <button class="btn-order btn-move-down" title="Переместить ниже" ${idx === this.rounds.length - 1 ? 'disabled' : ''}>▼</button>
            </div>
          </div>

          <div>
            <span class="field-label">Тип тура</span>
            <select class="form-select select-type">
              <option value="qualifying" ${round.type === 'qualifying' ? 'selected' : ''}>Отборочный</option>
              <option value="final" ${round.type === 'final' ? 'selected' : ''}>Финал</option>
              <option value="supergame" ${round.type === 'supergame' ? 'selected' : ''}>Суперигра</option>
            </select>
          </div>

          <div>
            <span class="field-label">Вопрос тура</span>
            <select class="form-select select-question">
              ${qOptions}
            </select>
          </div>

          <div>
            <span class="field-label">Барабан</span>
            <select class="form-select select-wheel">
              ${wOptions}
            </select>
          </div>

          <div>
            <span class="field-label">Приз</span>
            <select class="form-select select-prize">
              ${pOptions}
            </select>
          </div>

          <div>
            <span class="field-label">&nbsp;</span>
            <button class="btn-delete-sector btn-delete-round" title="Удалить тур">×</button>
          </div>
        `;

        this.bindCardEvents(card, idx);
        this.roundsList.appendChild(card);
      });
    }

    bindCardEvents(card, idx) {
      const btnUp = card.querySelector('.btn-move-up');
      const btnDown = card.querySelector('.btn-move-down');
      const btnDel = card.querySelector('.btn-delete-round');
      const selectType = card.querySelector('.select-type');
      const selectQuestion = card.querySelector('.select-question');
      const selectWheel = card.querySelector('.select-wheel');
      const selectPrize = card.querySelector('.select-prize');

      btnUp.addEventListener('click', () => {
        if (idx > 0) {
          const temp = this.rounds[idx];
          this.rounds[idx] = this.rounds[idx - 1];
          this.rounds[idx - 1] = temp;
          this.renderRounds();
        }
      });

      btnDown.addEventListener('click', () => {
        if (idx < this.rounds.length - 1) {
          const temp = this.rounds[idx];
          this.rounds[idx] = this.rounds[idx + 1];
          this.rounds[idx + 1] = temp;
          this.renderRounds();
        }
      });

      selectType.addEventListener('change', () => {
        this.rounds[idx].type = selectType.value;
        card.className = `round-card type-${selectType.value}`;
      });

      selectQuestion.addEventListener('change', () => {
        const val = selectQuestion.value;
        this.rounds[idx].question_id = val ? parseInt(val, 10) : null;
      });

      selectWheel.addEventListener('change', () => {
        const val = selectWheel.value;
        this.rounds[idx].wheel_id = val ? parseInt(val, 10) : null;
      });

      selectPrize.addEventListener('change', () => {
        const val = selectPrize.value;
        this.rounds[idx].prize_id = val ? parseInt(val, 10) : null;
      });

      btnDel.addEventListener('click', async () => {
        if (!confirm(`Удалить тур #${idx + 1}?`)) return;
        const roundId = this.rounds[idx].id;
        try {
          const resp = await fetch(`/studio/api/rounds/${roundId}/`, {
            method: 'DELETE',
            headers: {
              'X-CSRFToken': window.CSRF_TOKEN,
            },
          });
          if (!resp.ok) throw new Error('Ошибка удаления тура');
          this.rounds.splice(idx, 1);
          this.renderRounds();
          this.updateStats();
          this.showToast('Тур удалён');
        } catch (err) {
          this.showToast(err.message, true);
        }
      });
    }

    updateStats() {
      if (this.statCount) {
        this.statCount.textContent = this.rounds.length;
      }
    }

    bindEvents() {
      if (this.eventSelect) {
        this.eventSelect.addEventListener('change', () => {
          const newEventId = parseInt(this.eventSelect.value, 10);
          if (newEventId) {
            this.eventId = newEventId;
            this.loadScenario(newEventId);
          }
        });
      }

      if (this.btnAddRound) {
        this.btnAddRound.addEventListener('click', () => this.addRound());
      }

      if (this.btnSaveScenario) {
        this.btnSaveScenario.addEventListener('click', () => this.saveScenario());
      }
    }

    async addRound() {
      try {
        const defaultQuestionId = this.questions.length > 0 ? this.questions[0].id : null;
        const defaultWheelId = this.wheels.length > 0 ? this.wheels[0].id : null;

        const resp = await fetch(`/studio/api/events/${this.eventId}/rounds/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': window.CSRF_TOKEN,
          },
          body: JSON.stringify({
            type: 'qualifying',
            question_id: defaultQuestionId,
            wheel_id: defaultWheelId,
          }),
        });

        const data = await resp.json();
        if (!resp.ok) throw new Error(data.message || 'Ошибка создания тура');

        this.rounds.push(data.round);
        this.renderRounds();
        this.updateStats();
        this.showToast(`Тур #${this.rounds.length} добавлен`);
      } catch (err) {
        this.showToast(err.message, true);
      }
    }

    async saveScenario() {
      if (this.isSaving) return;
      this.isSaving = true;
      this.btnSaveScenario.disabled = true;
      this.btnSaveScenario.innerHTML = '<span class="icon">⏳</span> Сохранение...';

      try {
        // 1. Save reordered sequence
        const roundIds = this.rounds.map(r => r.id);
        const reorderResp = await fetch(`/studio/api/events/${this.eventId}/rounds/reorder/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': window.CSRF_TOKEN,
          },
          body: JSON.stringify({ round_ids: roundIds }),
        });

        if (!reorderResp.ok) {
          const errData = await reorderResp.json();
          throw new Error(errData.message || 'Ошибка сохранения порядка туров');
        }

        // 2. Save individual round attributes
        for (const round of this.rounds) {
          await fetch(`/studio/api/rounds/${round.id}/`, {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': window.CSRF_TOKEN,
            },
            body: JSON.stringify({
              type: round.type,
              question_id: round.question_id,
              wheel_id: round.wheel_id,
              prize_id: round.prize_id,
            }),
          });
        }

        this.showToast('Сценарий успешно сохранён!');
      } catch (err) {
        this.showToast(err.message, true);
      } finally {
        this.isSaving = false;
        this.btnSaveScenario.disabled = false;
        this.btnSaveScenario.innerHTML = '<span class="icon">💾</span> Сохранить сценарий';
      }
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  document.addEventListener('DOMContentLoaded', () => {
    window.scenarioApp = new ScenarioApp();
  });
})();
