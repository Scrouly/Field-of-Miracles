/**
 * swipe.js — Обработка тач-свайпа и вращения барабана пальцем/мышью.
 *
 * Требования (Задача 9):
 *  - Свайп по окружности задаёт угловую скорость;
 *  - Минимальный порог скорости для отсечения случайных касаний ладонью;
 *  - Интеграция с WheelCanvas и воспроизведение трещотки через AudioManager.
 */

(function () {
  'use strict';

  class SwipeController {
    constructor(wheelCanvasInstance, options = {}) {
      this.wheel = wheelCanvasInstance;
      this.canvas = this.wheel.canvas;
      this.onSpinTrigger = options.onSpinTrigger || null;

      this.isDragging = false;
      this.startAngle = 0;
      this.lastAngle = 0;
      this.lastTime = 0;
      this.angularVelocity = 0; // радиан/мс

      // Минимальный порог угловой скорости для запуска полноценного вращения
      this.minThreshold = options.minThreshold || 0.0015; // радиан/мс (около 1.5 рад/сек)

      this.initEvents();
    }

    getCenter() {
      const rect = this.canvas.getBoundingClientRect();
      return {
        cx: rect.left + rect.width / 2,
        cy: rect.top + rect.height / 2,
      };
    }

    getPointerAngle(clientX, clientY) {
      const { cx, cy } = this.getCenter();
      return Math.atan2(clientY - cy, clientX - cx);
    }

    initEvents() {
      this.canvas.addEventListener('pointerdown', (e) => this.onPointerDown(e));
      window.addEventListener('pointermove', (e) => this.onPointerMove(e));
      window.addEventListener('pointerup', (e) => this.onPointerUp(e));
      window.addEventListener('pointercancel', (e) => this.onPointerUp(e));
    }

    onPointerDown(e) {
      if (this.wheel.isSpinning) return;

      this.isDragging = true;
      this.startAngle = this.getPointerAngle(e.clientX, e.clientY);
      this.lastAngle = this.startAngle;
      this.lastTime = performance.now();
      this.angularVelocity = 0;

      // Разблокируем звук по жесту касания
      if (window.audioManager) {
        window.audioManager.unlock();
      }
    }

    onPointerMove(e) {
      if (!this.isDragging) return;

      const now = performance.now();
      const currentAngle = this.getPointerAngle(e.clientX, e.clientY);
      const dt = now - this.lastTime;

      if (dt > 8) { // опрос каждые ~8-16 мс
        let dTheta = currentAngle - this.lastAngle;

        // Коррекция перехода через границы -PI / +PI
        if (dTheta > Math.PI) dTheta -= 2 * Math.PI;
        if (dTheta < -Math.PI) dTheta += 2 * Math.PI;

        this.angularVelocity = dTheta / dt;
        this.lastAngle = currentAngle;
        this.lastTime = now;
      }
    }

    onPointerUp(_e) {
      if (!this.isDragging) return;
      this.isDragging = false;

      const speed = Math.abs(this.angularVelocity);

      // Проверка минимального порога скорости для отсечения случайных касаний
      if (speed >= this.minThreshold) {
        // Достаточный свайп — запускаем вращение!
        if (typeof this.onSpinTrigger === 'function') {
          this.onSpinTrigger(speed);
        }
      }
    }
  }

  window.SwipeController = SwipeController;
})();
