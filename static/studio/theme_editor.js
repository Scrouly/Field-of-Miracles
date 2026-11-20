/**
 * theme_editor.js — Редактор оформления, звуков и витрины призов (Task 15).
 */

(function () {
  'use strict';

  const PRESETS = {
    dolomite: {
      bg_main: '#0b132b',
      bg_card: '#1c2541',
      bg_card_light: '#243356',
      color_gold: '#f4c430',
      color_text: '#ffffff',
      color_accent: '#2a9d8f',
    },
    anniversary: {
      bg_main: '#1a120b',
      bg_card: '#2a1e17',
      bg_card_light: '#3e2c22',
      color_gold: '#ffd700',
      color_text: '#ffffff',
      color_accent: '#e76f51',
    },
    high_contrast: {
      bg_main: '#000000',
      bg_card: '#111111',
      bg_card_light: '#222222',
      color_gold: '#ffdd00',
      color_text: '#ffffff',
      color_accent: '#00ffff',
    },
  };

  class ThemeEditorApp {
    constructor() {
      this.themeId = window.CURRENT_THEME_ID;
      this.colors = {};
      this.audioManager = window.AudioManager ? new window.AudioManager() : null;

      this.initElements();
      this.bindEvents();
      this.collectColorsFromDOM();
      this.updateLiveMockup();
    }

    initElements() {
      this.themeSelect = document.getElementById('theme-select');
      this.btnSaveTheme = document.getElementById('btn-save-theme');
      this.mockup = document.getElementById('mini-mockup');
      this.toastEl = document.getElementById('toast');
    }

    showToast(msg, isError = false) {
      if (!this.toastEl) return;
      this.toastEl.textContent = msg;
      this.toastEl.className = 'toast ' + (isError ? 'error' : 'success');
      setTimeout(() => {
        this.toastEl.className = 'toast hidden';
      }, 3500);
    }

    collectColorsFromDOM() {
      document.querySelectorAll('.input-color-picker').forEach(picker => {
        const varName = picker.dataset.var;
        if (varName) {
          this.colors[varName] = picker.value;
        }
      });
    }

    updateLiveMockup() {
      if (!this.mockup) return;
      Object.entries(this.colors).forEach(([key, val]) => {
        const cssVar = '--' + key.replace('_', '-');
        this.mockup.style.setProperty(cssVar, val);
      });
    }

    applyPreset(presetName) {
      const preset = PRESETS[presetName];
      if (!preset) return;

      Object.entries(preset).forEach(([key, val]) => {
        this.colors[key] = val;
        const picker = document.querySelector(`.input-color-picker[data-var="${key}"]`);
        const hex = document.querySelector(`.input-color-hex[data-var="${key}"]`);
        if (picker) picker.value = val;
        if (hex) hex.value = val;
      });

      this.updateLiveMockup();
      this.showToast(`Применена палитра «${presetName}»`);
    }

    bindEvents() {
      // Color pickers sync
      document.querySelectorAll('.color-cell-wrapper').forEach(wrapper => {
        const picker = wrapper.querySelector('.input-color-picker');
        const hex = wrapper.querySelector('.input-color-hex');
        const varName = picker.dataset.var;

        picker.addEventListener('input', () => {
          hex.value = picker.value;
          this.colors[varName] = picker.value;
          this.updateLiveMockup();
        });

        hex.addEventListener('input', () => {
          if (/^#[0-9a-fA-F]{6}$/.test(hex.value)) {
            picker.value = hex.value;
            this.colors[varName] = hex.value;
            this.updateLiveMockup();
          }
        });
      });

      // Preset buttons
      document.querySelectorAll('.btn-preset').forEach(btn => {
        btn.addEventListener('click', () => {
          this.applyPreset(btn.dataset.preset);
        });
      });

      // Sound test buttons
      document.querySelectorAll('.btn-test-sound').forEach(btn => {
        btn.addEventListener('click', () => {
          const sound = btn.dataset.sound;
          if (this.audioManager) {
            this.audioManager.unlock().then(() => {
              this.audioManager.play(sound);
            });
          }
        });
      });

      // Save theme
      if (this.btnSaveTheme) {
        this.btnSaveTheme.addEventListener('click', () => this.saveTheme());
      }

      // Theme selector switch
      if (this.themeSelect) {
        this.themeSelect.addEventListener('change', () => {
          const newId = parseInt(this.themeSelect.value, 10);
          if (newId) {
            window.location.href = `/studio/theme/${newId}/`;
          }
        });
      }
    }

    async saveTheme() {
      this.collectColorsFromDOM();
      this.btnSaveTheme.disabled = true;
      this.btnSaveTheme.innerHTML = '<span class="icon">⏳</span> Сохранение...';

      try {
        const resp = await fetch(`/studio/api/themes/${this.themeId}/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': window.CSRF_TOKEN,
          },
          body: JSON.stringify({ colors: this.colors }),
        });

        const data = await resp.json();
        if (!resp.ok) throw new Error(data.message || 'Ошибка сохранения темы');

        this.showToast('Тема успешно сохранена! Изменения применены к табло.');
      } catch (err) {
        this.showToast(err.message, true);
      } finally {
        this.btnSaveTheme.disabled = false;
        this.btnSaveTheme.innerHTML = '<span class="icon">💾</span> Сохранить тему';
      }
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    window.themeEditorApp = new ThemeEditorApp();
  });
})();
