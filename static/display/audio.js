/**
 * audio.js — Звуковой менеджер «Поле чудес» на Web Audio API.
 *
 * Требования (Задача 9):
 *  - Работает строго офлайн без внешних библиотек;
 *  - Трещотка барабана: синтез реалистичного щелчка штифта о стрелку;
 *  - Звук разблокируется пользовательским жестом (кнопка запуска / первый тап);
 *  - Защита от автовоспроизведения (AudioContext разблокируется по клику).
 */

(function () {
  'use strict';

  class AudioManager {
    constructor() {
      this.ctx = null;
      this.isUnlocked = false;
      this.volume = 0.8;

      this.initListeners();
    }

    initAudioContext() {
      if (!this.ctx) {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (AudioCtx) {
          this.ctx = new AudioCtx();
        }
      }
    }

    /**
     * Разблокировка звука при первом пользовательском жесте.
     */
    async unlock() {
      this.initAudioContext();
      if (!this.ctx) return false;

      if (this.ctx.state === 'suspended') {
        try {
          await this.ctx.resume();
        } catch (err) {
          console.warn('AudioContext resume failed:', err);
        }
      }

      this.isUnlocked = this.ctx.state === 'running';
      return this.isUnlocked;
    }

    initListeners() {
      // Автоматическая попытка разблокировки при первом клике/тапе в любом месте окна
      const unlockHandler = () => {
        this.unlock().then((ok) => {
          if (ok) {
            window.removeEventListener('pointerdown', unlockHandler);
            window.removeEventListener('keydown', unlockHandler);
          }
        });
      };

      window.addEventListener('pointerdown', unlockHandler, { once: true });
      window.addEventListener('keydown', unlockHandler, { once: true });
    }

    /**
     * Реалистичный щелчок трещотки барабана (Web Audio API синтез).
     * Частота и тембр имитируют удар деревянного штифта о пластиковую/металлическую стрелку.
     */
    playRatchetClick(pitch = 1.0) {
      if (!this.ctx || this.ctx.state !== 'running') return;

      const now = this.ctx.currentTime;

      // 1. Короткий импульсный щелчок (резонансный фильтр + шум)
      const bufferSize = Math.floor(this.ctx.sampleRate * 0.025); // 25 мс
      const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
      const data = buffer.getChannelData(0);

      // Генерация затухающего импульса щелчка
      for (let i = 0; i < bufferSize; i++) {
        const t = i / bufferSize;
        // Экспоненциальное затухание
        const decay = Math.exp(-t * 22);
        // Смесь высокочастотного щелчка и древесного тона
        data[i] = (Math.random() * 2 - 1) * decay;
      }

      const noise = this.ctx.createBufferSource();
      noise.buffer = buffer;

      // Полосовой фильтр для имитации тембра дерева / металла
      const filter = this.ctx.createBiquadFilter();
      filter.type = 'bandpass';
      filter.frequency.setValueAtTime(1400 * pitch, now);
      filter.Q.setValueAtTime(3.5, now);

      // Регулятор громкости щелчка
      const gain = this.ctx.createGain();
      gain.gain.setValueAtTime(0.4 * this.volume, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.025);

      noise.connect(filter);
      filter.connect(gain);
      gain.connect(this.ctx.destination);

      noise.start(now);
      noise.stop(now + 0.025);
    }

    /**
     * Звук сектора «Банкрот» (нисходящий глиссандо-тон).
     */
    playBankrupt() {
      if (!this.ctx || this.ctx.state !== 'running') return;
      const now = this.ctx.currentTime;

      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(260, now);
      osc.frequency.exponentialRampToValueAtTime(70, now + 0.8);

      gain.gain.setValueAtTime(0.3 * this.volume, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.8);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      osc.start(now);
      osc.stop(now + 0.8);
    }

    /**
     * Звук верной буквы / сектора (мажорный победный аккорд).
     */
    playHit() {
      if (!this.ctx || this.ctx.state !== 'running') return;
      const freqs = [523.25, 659.25, 783.99]; // C5, E5, G5
      const now = this.ctx.currentTime;

      freqs.forEach((f, idx) => {
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.type = 'triangle';
        osc.frequency.setValueAtTime(f, now + idx * 0.06);

        gain.gain.setValueAtTime(0.2 * this.volume, now + idx * 0.06);
        gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.06 + 0.4);

        osc.connect(gain);
        gain.connect(this.ctx.destination);

        osc.start(now + idx * 0.06);
        osc.stop(now + idx * 0.06 + 0.4);
      });
    }

    /**
     * Воспроизведение звука по имени триггера.
     */
    play(soundName) {
      if (!soundName) return;
      switch (soundName.toLowerCase()) {
        case 'bankrupt':
          this.playBankrupt();
          break;
        case 'hit':
        case 'letter_open':
        case 'win':
          this.playHit();
          break;
        case 'sector_plus':
        case 'box_game':
          if (!this.ctx || this.ctx.state !== 'running') return;
          [523.25, 659.25, 783.99, 1046.5].forEach((f, i) => {
            const now = this.ctx.currentTime;
            const osc = this.ctx.createOscillator();
            const gain = this.ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(f, now + i * 0.08);
            gain.gain.setValueAtTime(0.25 * this.volume, now + i * 0.08);
            gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.08 + 0.3);
            osc.connect(gain);
            gain.connect(this.ctx.destination);
            osc.start(now + i * 0.08);
            osc.stop(now + i * 0.08 + 0.3);
          });
          break;
        case 'miss':
          if (!this.ctx || this.ctx.state !== 'running') return;
          const now = this.ctx.currentTime;
          const osc = this.ctx.createOscillator();
          const gain = this.ctx.createGain();
          osc.type = 'sawtooth';
          osc.frequency.setValueAtTime(130, now);
          osc.frequency.exponentialRampToValueAtTime(90, now + 0.35);
          gain.gain.setValueAtTime(0.2 * this.volume, now);
          gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
          osc.connect(gain);
          gain.connect(this.ctx.destination);
          osc.start(now);
          osc.stop(now + 0.35);
          break;
        default:
          break;
      }
    }
  }

  window.AudioManager = AudioManager;
})();
