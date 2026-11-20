/**
 * timer.js — Круговой таймер суперигры на SVG (Задача 14).
 *
 * Требования:
 *  - Круговой таймер 30 или 60 секунд (из параметров суперигры);
 *  - Отсчёт ведётся по абсолютному времени сервера, а не вкладки;
 *  - Сворачивание / неактивность вкладки не сбивает расчёт;
 *  - При достижении 0 звучит гонг.
 */

(function () {
  'use strict';

  class SupergameTimer {
    constructor(displayManager) {
      this.display = displayManager;
      this.timerEndTimestamp = null;
      this.timerDuration = 60;
      this.serverOffsetMs = 0;
      this.isRunning = false;
      this.hasFiredTimeUp = false;
      this.animFrameId = null;

      this.createDOM();
    }

    createDOM() {
      this.container = document.createElement('div');
      this.container.id = 'supergame-timer-container';
      this.container.className = 'supergame-timer-container hidden';

      const radius = 68;
      const circumference = 2 * Math.PI * radius;
      this.circumference = circumference;

      this.container.innerHTML = `
        <div class="timer-box">
          <svg class="timer-svg" width="160" height="160" viewBox="0 0 160 160">
            <circle class="timer-track" cx="80" cy="80" r="${radius}"></circle>
            <circle class="timer-progress" cx="80" cy="80" r="${radius}"
              stroke-dasharray="${circumference}"
              stroke-dashoffset="0"></circle>
          </svg>
          <div class="timer-text-wrap">
            <span class="timer-seconds" id="timer-seconds">60</span>
            <span class="timer-unit">сек</span>
          </div>
        </div>
      `;

      document.body.appendChild(this.container);

      this.progressCircle = this.container.querySelector('.timer-progress');
      this.secondsText = this.container.querySelector('#timer-seconds');
    }

    /**
     * Синхронизация часов сервера и клиента.
     */
    syncServerTime(serverEpochSeconds) {
      if (typeof serverEpochSeconds === 'number') {
        const clientNowMs = Date.now();
        const serverNowMs = serverEpochSeconds * 1000;
        this.serverOffsetMs = serverNowMs - clientNowMs;
      }
    }

    getEstimatedServerTime() {
      return (Date.now() + this.serverOffsetMs) / 1000;
    }

    update(state, serverTime) {
      if (!state) return;

      if (serverTime) {
        this.syncServerTime(serverTime);
      }

      // Check if supergame is in thinking / countdown phase
      const isSupergameThinking = (
        state.is_supergame &&
        state.phase === 'supergame_thinking' &&
        state.timer_end_timestamp != null
      );

      if (isSupergameThinking) {
        this.timerEndTimestamp = state.timer_end_timestamp;
        this.timerDuration = state.timer_duration || 60;
        this.start();
      } else {
        this.stop();
      }
    }

    start() {
      this.container.classList.remove('hidden');
      if (this.isRunning) return;

      this.isRunning = true;
      this.hasFiredTimeUp = false;

      const tick = () => {
        if (!this.isRunning) return;

        const now = this.getEstimatedServerTime();
        const remaining = Math.max(0, this.timerEndTimestamp - now);
        const ceilSec = Math.ceil(remaining);

        // Update display text
        if (this.secondsText) {
          this.secondsText.textContent = ceilSec;
        }

        // Update circular ring stroke
        const progressFrac = Math.min(1, Math.max(0, remaining / this.timerDuration));
        const offset = this.circumference * (1 - progressFrac);
        if (this.progressCircle) {
          this.progressCircle.style.strokeDashoffset = offset;
        }

        // Warning state (< 10 seconds)
        if (ceilSec <= 10) {
          this.container.classList.add('timer-warning');
        } else {
          this.container.classList.remove('timer-warning');
        }

        // Time up check
        if (remaining <= 0) {
          this.onTimeExpired();
          return;
        }

        this.animFrameId = requestAnimationFrame(tick);
      };

      this.animFrameId = requestAnimationFrame(tick);
    }

    onTimeExpired() {
      this.stop();
      if (this.hasFiredTimeUp) return;
      this.hasFiredTimeUp = true;

      // Play Gong sound!
      if (this.display.audioManager && typeof this.display.audioManager.playGong === 'function') {
        this.display.audioManager.playGong();
      }

      // Notify server of time-up
      this.display.sendAction({
        type: 'SUPERGAME_TIME_UP',
      });
    }

    stop() {
      this.isRunning = false;
      if (this.animFrameId) {
        cancelAnimationFrame(this.animFrameId);
        this.animFrameId = null;
      }
      this.container.classList.add('hidden');
      this.container.classList.remove('timer-warning');
    }
  }

  window.SupergameTimer = SupergameTimer;
})();
