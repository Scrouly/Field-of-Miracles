/**
 * wheel.js — Барабан «Поле чудес» на HTML5 <canvas>.
 *
 * Требования (Задача 7):
 *  - 16–20 секторов с чередующимися цветами;
 *  - Текст вдоль радиуса каждого сектора;
 *  - Чёткая отрисовка на экранах с высоким DPI (devicePixelRatio);
 *  - Интерфейс animateTo(index, durationMs) с плавным замедлением;
 *  - Событие / коллбек при пересечении границы сектора (для трещотки).
 */

(function () {
  'use strict';

  // 16 секторов по умолчанию (контентная схема ОАО «Доломит»)
  const DEFAULT_SECTORS = [
    { label: '100', value: 100, color: '#1f4e5b' },
    { label: '300', value: 300, color: '#243356' },
    { label: '150', value: 150, color: '#162447' },
    { label: '200', value: 200, color: '#2a9d8f' },
    { label: '500', value: 500, color: '#d97706' },
    { label: '100', value: 100, color: '#1f4e5b' },
    { label: '250', value: 250, color: '#243356' },
    { label: '400', value: 400, color: '#3b82f6' },
    { label: '150', value: 150, color: '#162447' },
    { label: '200', value: 200, color: '#2a9d8f' },
    { label: '600', value: 600, color: '#8b5cf6' },
    { label: '350', value: 350, color: '#243356' },
    { label: '100', value: 100, color: '#1f4e5b' },
    { label: '300', value: 300, color: '#162447' },
    { label: '750', value: 750, color: '#ef4444' },
    { label: '250', value: 250, color: '#2a9d8f' },
  ];

  class WheelCanvas {
    constructor(canvasElement, options = {}) {
      this.canvas = canvasElement;
      if (!this.canvas) {
        throw new Error('Canvas element not provided');
      }

      this.ctx = this.canvas.getContext('2d');
      this.sectors = options.sectors || DEFAULT_SECTORS;
      this.onTick = options.onTick || null; // callback(sectorIndex) при пересечении границ
      this.onFinish = options.onFinish || null;

      this.size = options.size || 600;
      this.radius = this.size / 2;

      this.currentAngle = 0; // в радианах
      this.isSpinning = false;
      this.lastTickSector = -1;

      this.setupDPI();
      this.draw();
    }

    setupDPI() {
      const dpr = window.devicePixelRatio || 1;
      this.dpr = dpr;

      this.canvas.width = Math.round(this.size * dpr);
      this.canvas.height = Math.round(this.size * dpr);
      this.canvas.style.width = `${this.size}px`;
      this.canvas.style.height = `${this.size}px`;

      this.ctx.setTransform(1, 0, 0, 1, 0, 0);
      this.ctx.scale(dpr, dpr);
    }

    setSectors(sectors) {
      if (sectors && sectors.length > 0) {
        this.sectors = sectors;
        this.draw();
      }
    }

    /**
     * Отрисовка барабана.
     */
    draw(angle = this.currentAngle) {
      const ctx = this.ctx;
      const size = this.size;
      const r = this.radius;
      const numSectors = this.sectors.length;
      const sliceAngle = (2 * Math.PI) / numSectors;

      ctx.clearRect(0, 0, size, size);

      ctx.save();
      ctx.translate(r, r);
      ctx.rotate(angle);

      // 1. Отрисовка секторов
      for (let i = 0; i < numSectors; i++) {
        const sector = this.sectors[i];
        const startA = i * sliceAngle;
        const endA = startA + sliceAngle;

        // Фон сектора
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.arc(0, 0, r - 12, startA, endA);
        ctx.closePath();
        ctx.fillStyle = sector.color || (i % 2 === 0 ? '#1f4e5b' : '#243356');
        ctx.fill();

        // Разделительная линия между секторами
        ctx.lineWidth = 2;
        ctx.strokeStyle = 'rgba(244, 196, 48, 0.4)';
        ctx.stroke();

        // 2. Текст вдоль радиуса сектора
        ctx.save();
        const midA = startA + sliceAngle / 2;
        ctx.rotate(midA);

        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 22px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';
        ctx.shadowColor = 'rgba(0, 0, 0, 0.7)';
        ctx.shadowBlur = 4;

        // Рисуем надпись сектора вдоль радиуса (с отступом от внешнего края)
        ctx.fillText(String(sector.label), r - 36, 0);

        ctx.restore();
      }

      // 3. Внешний обод с колышками (штифтами)
      ctx.restore(); // Сброс вращения колеса для обода

      // Золотой внешний обод
      ctx.save();
      ctx.translate(r, r);

      ctx.beginPath();
      ctx.arc(0, 0, r - 6, 0, 2 * Math.PI);
      ctx.lineWidth = 12;
      ctx.strokeStyle = '#f4c430';
      ctx.stroke();

      // Штифты по окружности (вращаются вместе с колесом)
      ctx.rotate(angle);
      for (let i = 0; i < numSectors; i++) {
        const pegAngle = i * sliceAngle;
        const px = (r - 12) * Math.cos(pegAngle);
        const py = (r - 12) * Math.sin(pegAngle);

        ctx.beginPath();
        ctx.arc(px, py, 4, 0, 2 * Math.PI);
        ctx.fillStyle = '#ffffff';
        ctx.shadowColor = '#000000';
        ctx.shadowBlur = 4;
        ctx.fill();
      }

      // Центральная ступица барабана (золотой диск с градиентом)
      ctx.restore();
      ctx.save();
      ctx.translate(r, r);

      const hubGrad = ctx.createRadialGradient(0, 0, 10, 0, 0, 50);
      hubGrad.addColorStop(0, '#ffe066');
      hubGrad.addColorStop(0.7, '#d4af37');
      hubGrad.addColorStop(1, '#855800');

      ctx.beginPath();
      ctx.arc(0, 0, 48, 0, 2 * Math.PI);
      ctx.fillStyle = hubGrad;
      ctx.shadowColor = 'rgba(0, 0, 0, 0.6)';
      ctx.shadowBlur = 12;
      ctx.fill();

      // Внутреннее золотое кольцо ступицы
      ctx.beginPath();
      ctx.arc(0, 0, 24, 0, 2 * Math.PI);
      ctx.fillStyle = '#0b132b';
      ctx.fill();
      ctx.lineWidth = 3;
      ctx.strokeStyle = '#f4c430';
      ctx.stroke();

      ctx.restore();

      // 4. Стрелка-указатель вверху (на 12 часов, указывает вниз на колесо)
      this.drawPointer();
    }

    drawPointer() {
      const ctx = this.ctx;
      const r = this.radius;

      ctx.save();
      ctx.translate(r, 6);

      ctx.beginPath();
      ctx.moveTo(-16, 0);
      ctx.lineTo(16, 0);
      ctx.lineTo(0, 34);
      ctx.closePath();

      ctx.fillStyle = '#ef4444';
      ctx.shadowColor = 'rgba(0, 0, 0, 0.7)';
      ctx.shadowBlur = 8;
      ctx.fill();

      ctx.lineWidth = 3;
      ctx.strokeStyle = '#ffffff';
      ctx.stroke();

      ctx.restore();
    }

    /**
     * Определение индекса сектора под стрелкой при заданном угле поворота.
     * Стрелка находится вверху (угол -PI / 2 или 3*PI/2).
     */
    getSectorAtPointer(angle) {
      const numSectors = this.sectors.length;
      const sliceAngle = (2 * Math.PI) / numSectors;

      // Нормализуем угол поворота в [0, 2*PI)
      let norm = (angle % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI);

      // Стрелка на 12 часов (угол -PI/2 = 3*PI/2 в системе координат холста)
      // Сектор i расположен в [i*slice, (i+1)*slice] при угле поворота 0.
      // При повороте колеса на angle, под стрелкой (3*PI/2) оказывается сектор:
      let pointerAngle = (3 * Math.PI / 2 - norm + 2 * Math.PI) % (2 * Math.PI);
      const index = Math.floor(pointerAngle / sliceAngle) % numSectors;
      return index;
    }

    /**
     * Анимация вращения к заданному сектору index.
     *
     * @param {number} targetIndex — целевой сектор [0..numSectors-1]
     * @param {number} durationMs — длительность в мс (по умолчанию 4500)
     * @returns {Promise<number>} — промис, возвращающий targetIndex по завершении
     */
    animateTo(targetIndex, durationMs = 4500) {
      if (this.isSpinning) {
        return Promise.reject(new Error('Wheel is already spinning'));
      }

      this.isSpinning = true;
      const numSectors = this.sectors.length;
      const sliceAngle = (2 * Math.PI) / numSectors;

      // Рассчитываем целевой угол так, чтобы середина сектора targetIndex оказалась под стрелкой (3*PI/2)
      // pointerAngle = 3*PI/2 -> targetMidAngle = targetIndex * sliceAngle + sliceAngle / 2
      // norm = 3*PI/2 - targetMidAngle
      const targetMidAngle = targetIndex * sliceAngle + sliceAngle / 2;
      let desiredAngle = (3 * Math.PI / 2 - targetMidAngle) % (2 * Math.PI);
      if (desiredAngle < 0) desiredAngle += 2 * Math.PI;

      // Текущий нормализованный угол
      const currentNorm = this.currentAngle % (2 * Math.PI);

      // Полные обороты (5-7 полных кругов для зрелищности)
      const fullRotations = 6 * 2 * Math.PI;
      let deltaAngle = desiredAngle - currentNorm;
      if (deltaAngle <= 0) deltaAngle += 2 * Math.PI;

      const startAngle = this.currentAngle;
      const totalDelta = fullRotations + deltaAngle;
      const startTime = performance.now();

      return new Promise((resolve) => {
        const frame = (now) => {
          const elapsed = now - startTime;
          const t = Math.min(1, elapsed / durationMs);

          // Easing: кубическое замедление (ease-out cubic / quartic)
          const ease = 1 - Math.pow(1 - t, 4);

          this.currentAngle = startAngle + totalDelta * ease;
          this.draw(this.currentAngle);

          // Проверка границы секторов для трещотки
          const currentSector = this.getSectorAtPointer(this.currentAngle);
          if (currentSector !== this.lastTickSector) {
            this.lastTickSector = currentSector;
            if (typeof this.onTick === 'function') {
              this.onTick(currentSector);
            }
          }

          if (t < 1) {
            requestAnimationFrame(frame);
          } else {
            this.isSpinning = false;
            this.currentAngle = startAngle + totalDelta;
            this.draw(this.currentAngle);

            if (typeof this.onFinish === 'function') {
              this.onFinish(targetIndex);
            }
            resolve(targetIndex);
          }
        };

        requestAnimationFrame(frame);
      });
    }
  }

  window.WheelCanvas = WheelCanvas;
})();
