/**
 * wheel_editor.js — Интерактивный редактор барабана с живым предпросмотром на Canvas.
 */

(function () {
  'use strict';

  // Dolomite palette for alternating colors
  const DOLOMITE_PALETTE = ['#1f4e5b', '#243356', '#162447', '#2a9d8f', '#d97706', '#3b82f6'];

  const DEFAULT_16_SECTORS = [
    { label: '100', value: 100, color: '#1f4e5b', weight: 1, effect_id: null },
    { label: '300', value: 300, color: '#243356', weight: 1, effect_id: null },
    { label: '150', value: 150, color: '#162447', weight: 1, effect_id: null },
    { label: '200', value: 200, color: '#2a9d8f', weight: 1, effect_id: null },
    { label: '500', value: 500, color: '#d97706', weight: 1, effect_id: null },
    { label: '100', value: 100, color: '#1f4e5b', weight: 1, effect_id: null },
    { label: '250', value: 250, color: '#243356', weight: 1, effect_id: null },
    { label: '400', value: 400, color: '#3b82f6', weight: 1, effect_id: null },
    { label: '150', value: 150, color: '#162447', weight: 1, effect_id: null },
    { label: '200', value: 200, color: '#2a9d8f', weight: 1, effect_id: null },
    { label: '600', value: 600, color: '#8b5cf6', weight: 1, effect_id: null },
    { label: '350', value: 350, color: '#243356', weight: 1, effect_id: null },
    { label: '100', value: 100, color: '#1f4e5b', weight: 1, effect_id: null },
    { label: '300', value: 300, color: '#162447', weight: 1, effect_id: null },
    { label: '750', value: 750, color: '#ef4444', weight: 1, effect_id: null },
    { label: '250', value: 250, color: '#2a9d8f', weight: 1, effect_id: null },
  ];

  class WheelEditorApp {
    constructor() {
      this.currentWheelId = window.INITIAL_WHEEL_ID;
      this.sectors = [];
      this.effects = [];
      this.wheelCanvas = null;
      this.isSaving = false;

      this.initElements();
      this.initCanvas();
      this.bindEvents();

      if (this.currentWheelId) {
        this.loadWheel(this.currentWheelId);
      }
    }

    initElements() {
      this.wheelSelect = document.getElementById('wheel-select');
      this.btnNewWheel = document.getElementById('btn-new-wheel');
      this.wheelNameInput = document.getElementById('wheel-name-input');
      this.btnSaveWheel = document.getElementById('btn-save-wheel');
      this.btnAddSector = document.getElementById('btn-add-sector');
      this.btnAlternateColors = document.getElementById('btn-alternate-colors');
      this.btnDefault16 = document.getElementById('btn-default-16');
      this.sectorsTbody = document.getElementById('sectors-tbody');
      this.canvasEl = document.getElementById('wheel-preview-canvas');
      this.btnTestSpin = document.getElementById('btn-test-spin');
      this.spinResultText = document.getElementById('spin-result-text');
      this.toastEl = document.getElementById('toast');

      this.statCount = document.getElementById('stat-sectors-count');
      this.statPoints = document.getElementById('stat-points-sum');
      this.statWeight = document.getElementById('stat-total-weight');
    }

    initCanvas() {
      if (typeof window.WheelCanvas === 'function' && this.canvasEl) {
        this.wheelCanvas = new window.WheelCanvas(this.canvasEl, {
          size: 440,
          sectors: DEFAULT_16_SECTORS,
        });
      }
    }

    showToast(message, isError = false) {
      if (!this.toastEl) return;
      this.toastEl.textContent = message;
      this.toastEl.className = 'toast ' + (isError ? 'error' : 'success');
      setTimeout(() => {
        this.toastEl.className = 'toast hidden';
      }, 3500);
    }

    async loadWheel(wheelId) {
      try {
        const resp = await fetch(`/studio/api/wheels/${wheelId}/`);
        if (!resp.ok) {
          throw new Error('Ошибка загрузки данных барабана');
        }
        const data = await resp.json();
        this.currentWheelId = data.wheel.id;
        this.wheelNameInput.value = data.wheel.name;
        this.sectors = data.wheel.sectors.map(s => ({
          id: s.id,
          order: s.order,
          label: s.label,
          value: s.value,
          color: s.color || '#1f4e5b',
          weight: s.weight || 1,
          effect_id: s.effect_id,
        }));
        this.effects = data.effects || [];

        this.renderTable();
        this.updateStats();
        this.updatePreview();
      } catch (err) {
        this.showToast(err.message, true);
      }
    }

    renderTable() {
      if (!this.sectorsTbody) return;
      this.sectorsTbody.innerHTML = '';

      this.sectors.forEach((sector, idx) => {
        const tr = document.createElement('tr');
        tr.dataset.index = idx;

        // Effect options
        let effectOptions = '<option value="">(нет)</option>';
        this.effects.forEach(eff => {
          const selected = sector.effect_id === eff.id ? 'selected' : '';
          effectOptions += `<option value="${eff.id}" ${selected}>${eff.name}</option>`;
        });

        tr.innerHTML = `
          <td><strong>${idx + 1}</strong></td>
          <td>
            <div class="cell-order-btns">
              <button class="btn-order btn-move-up" title="Поднять" ${idx === 0 ? 'disabled' : ''}>▲</button>
              <button class="btn-order btn-move-down" title="Опустить" ${idx === this.sectors.length - 1 ? 'disabled' : ''}>▼</button>
            </div>
          </td>
          <td>
            <input type="text" class="input-cell input-label" value="${escapeHtml(sector.label)}" maxlength="30">
          </td>
          <td>
            <input type="number" class="input-cell input-value" value="${sector.value}">
          </td>
          <td>
            <div class="color-cell-wrapper">
              <input type="color" class="input-color-picker" value="${sector.color}">
              <input type="text" class="input-cell input-color-hex" value="${sector.color}" maxlength="7">
            </div>
          </td>
          <td>
            <input type="number" class="input-cell input-weight" value="${sector.weight}" min="1">
          </td>
          <td>
            <select class="input-cell select-effect">
              ${effectOptions}
            </select>
          </td>
          <td>
            <button class="btn-delete-sector" title="Удалить сектор">×</button>
          </td>
        `;

        this.bindRowEvents(tr, idx);
        this.sectorsTbody.appendChild(tr);
      });
    }

    bindRowEvents(tr, idx) {
      const labelInput = tr.querySelector('.input-label');
      const valInput = tr.querySelector('.input-value');
      const colorPicker = tr.querySelector('.input-color-picker');
      const colorHex = tr.querySelector('.input-color-hex');
      const weightInput = tr.querySelector('.input-weight');
      const selectEffect = tr.querySelector('.select-effect');
      const btnUp = tr.querySelector('.btn-move-up');
      const btnDown = tr.querySelector('.btn-move-down');
      const btnDel = tr.querySelector('.btn-delete-sector');

      labelInput.addEventListener('input', () => {
        this.sectors[idx].label = labelInput.value;
        this.updatePreview();
      });

      valInput.addEventListener('input', () => {
        this.sectors[idx].value = parseInt(valInput.value, 10) || 0;
        this.updateStats();
        this.updatePreview();
      });

      colorPicker.addEventListener('input', () => {
        colorHex.value = colorPicker.value;
        this.sectors[idx].color = colorPicker.value;
        this.updatePreview();
      });

      colorHex.addEventListener('input', () => {
        if (/^#[0-9a-fA-F]{6}$/.test(colorHex.value)) {
          colorPicker.value = colorHex.value;
          this.sectors[idx].color = colorHex.value;
          this.updatePreview();
        }
      });

      weightInput.addEventListener('input', () => {
        const w = parseInt(weightInput.value, 10);
        this.sectors[idx].weight = isNaN(w) || w < 1 ? 1 : w;
        this.updateStats();
      });

      selectEffect.addEventListener('change', () => {
        const effVal = selectEffect.value;
        this.sectors[idx].effect_id = effVal ? parseInt(effVal, 10) : null;
      });

      btnUp.addEventListener('click', () => {
        if (idx > 0) {
          const temp = this.sectors[idx];
          this.sectors[idx] = this.sectors[idx - 1];
          this.sectors[idx - 1] = temp;
          this.renderTable();
          this.updatePreview();
        }
      });

      btnDown.addEventListener('click', () => {
        if (idx < this.sectors.length - 1) {
          const temp = this.sectors[idx];
          this.sectors[idx] = this.sectors[idx + 1];
          this.sectors[idx + 1] = temp;
          this.renderTable();
          this.updatePreview();
        }
      });

      btnDel.addEventListener('click', () => {
        if (this.sectors.length <= 2) {
          this.showToast('Барабан должен содержать как минимум 2 сектора', true);
          return;
        }
        this.sectors.splice(idx, 1);
        this.renderTable();
        this.updateStats();
        this.updatePreview();
      });
    }

    updateStats() {
      const count = this.sectors.length;
      const points = this.sectors.reduce((sum, s) => sum + (s.value || 0), 0);
      const weight = this.sectors.reduce((sum, s) => sum + (s.weight || 1), 0);

      if (this.statCount) this.statCount.textContent = count;
      if (this.statPoints) this.statPoints.textContent = points;
      if (this.statWeight) this.statWeight.textContent = weight;
    }

    updatePreview() {
      if (!this.wheelCanvas) return;
      const previewSectors = this.sectors.map(s => ({
        label: s.label || '',
        value: s.value || 0,
        color: s.color || '#1f4e5b',
      }));
      this.wheelCanvas.setSectors(previewSectors);
    }

    bindEvents() {
      // Switch wheel
      if (this.wheelSelect) {
        this.wheelSelect.addEventListener('change', () => {
          const id = parseInt(this.wheelSelect.value, 10);
          if (id) {
            this.loadWheel(id);
          }
        });
      }

      // Add sector
      if (this.btnAddSector) {
        this.btnAddSector.addEventListener('click', () => {
          const color = DOLOMITE_PALETTE[this.sectors.length % DOLOMITE_PALETTE.length];
          this.sectors.push({
            label: '100',
            value: 100,
            color: color,
            weight: 1,
            effect_id: null,
          });
          this.renderTable();
          this.updateStats();
          this.updatePreview();
        });
      }

      // Alternate colors
      if (this.btnAlternateColors) {
        this.btnAlternateColors.addEventListener('click', () => {
          this.sectors.forEach((s, i) => {
            s.color = DOLOMITE_PALETTE[i % DOLOMITE_PALETTE.length];
          });
          this.renderTable();
          this.updatePreview();
          this.showToast('Цвета секций распределены по палитре Доломита');
        });
      }

      // Default 16
      if (this.btnDefault16) {
        this.btnDefault16.addEventListener('click', () => {
          if (!confirm('Заменить все сектора на 16 секторов по умолчанию?')) return;
          this.sectors = JSON.parse(JSON.stringify(DEFAULT_16_SECTORS));
          this.renderTable();
          this.updateStats();
          this.updatePreview();
        });
      }

      // Save wheel
      if (this.btnSaveWheel) {
        this.btnSaveWheel.addEventListener('click', () => this.saveWheel());
      }

      // New wheel
      if (this.btnNewWheel) {
        this.btnNewWheel.addEventListener('click', () => this.createNewWheel());
      }

      // Test spin
      if (this.btnTestSpin) {
        this.btnTestSpin.addEventListener('click', () => this.testSpin());
      }
    }

    async saveWheel() {
      if (this.isSaving) return;
      if (!this.currentWheelId) return;

      const name = (this.wheelNameInput.value || '').trim();
      if (!name) {
        this.showToast('Введите название барабана', true);
        return;
      }

      if (this.sectors.length < 2) {
        this.showToast('Барабан должен содержать хотя бы 2 сектора', true);
        return;
      }

      this.isSaving = true;
      this.btnSaveWheel.disabled = true;
      this.btnSaveWheel.innerHTML = '<span class="icon">⏳</span> Сохранение...';

      try {
        const payload = {
          name: name,
          sectors: this.sectors.map((s, idx) => ({
            order: idx,
            label: s.label,
            value: s.value,
            color: s.color,
            weight: s.weight,
            effect_id: s.effect_id,
          })),
        };

        const resp = await fetch(`/studio/api/wheels/${this.currentWheelId}/sectors/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': window.CSRF_TOKEN,
          },
          body: JSON.stringify(payload),
        });

        const data = await resp.json();
        if (!resp.ok) {
          throw new Error(data.message || 'Ошибка при сохранении барабана');
        }

        this.showToast('Барабан успешно сохранён!');
        // Update name in select dropdown
        if (this.wheelSelect) {
          const opt = this.wheelSelect.querySelector(`option[value="${this.currentWheelId}"]`);
          if (opt) {
            opt.textContent = `${name} (${this.sectors.length} сект.)`;
          }
        }
      } catch (err) {
        this.showToast(err.message, true);
      } finally {
        this.isSaving = false;
        this.btnSaveWheel.disabled = false;
        this.btnSaveWheel.innerHTML = '<span class="icon">💾</span> Сохранить барабан';
      }
    }

    async createNewWheel() {
      const name = prompt('Введите название нового барабана:', 'Барабан финала');
      if (!name || !name.trim()) return;

      try {
        const resp = await fetch('/studio/api/wheels/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': window.CSRF_TOKEN,
          },
          body: JSON.stringify({ name: name.trim(), with_defaults: true }),
        });

        const data = await resp.json();
        if (!resp.ok) {
          throw new Error(data.message || 'Ошибка создания барабана');
        }

        const newWheel = data.wheel;
        // Add to select
        const opt = document.createElement('option');
        opt.value = newWheel.id;
        opt.textContent = `${newWheel.name} (${newWheel.sector_count} сект.)`;
        this.wheelSelect.appendChild(opt);
        this.wheelSelect.value = newWheel.id;

        this.loadWheel(newWheel.id);
        this.showToast(`Барабан «${newWheel.name}» создан`);
      } catch (err) {
        this.showToast(err.message, true);
      }
    }

    testSpin() {
      if (!this.wheelCanvas || this.wheelCanvas.isSpinning || this.sectors.length === 0) return;

      // Choose random sector weighted
      const totalWeight = this.sectors.reduce((acc, s) => acc + (s.weight || 1), 0);
      let rand = Math.random() * totalWeight;
      let targetIdx = 0;
      for (let i = 0; i < this.sectors.length; i++) {
        rand -= (this.sectors[i].weight || 1);
        if (rand <= 0) {
          targetIdx = i;
          break;
        }
      }

      this.spinResultText.textContent = 'Вращение...';
      this.btnTestSpin.disabled = true;

      this.wheelCanvas.animateTo(targetIdx, 3600).then(() => {
        const winner = this.sectors[targetIdx];
        const eff = this.effects.find(e => e.id === winner.effect_id);
        const effText = eff ? ` (Эффект: ${eff.name})` : '';
        this.spinResultText.textContent = `Сектор #${targetIdx + 1}: «${winner.label}» [${winner.value} очков]${effText}`;
        this.btnTestSpin.disabled = false;
      });
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
    window.wheelEditorApp = new WheelEditorApp();
  });
})();
