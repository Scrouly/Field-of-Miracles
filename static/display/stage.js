/**
 * stage.js — Масштабирование виртуальной сцены 1920×1080 под любое разрешение мультиборда.
 *
 * Сцена сохраняет пропорцию 16:9 и центрируется в окне браузера.
 * Минимальная тач-цель в координатах сцены — не менее 64×64 px.
 */

(function () {
  'use strict';

  const VIRTUAL_WIDTH = 1920;
  const VIRTUAL_HEIGHT = 1080;

  class StageManager {
    constructor(stageSelector) {
      this.stage = document.querySelector(stageSelector);
      if (!this.stage) {
        throw new Error(`Stage element '${stageSelector}' not found`);
      }

      this.scale = 1.0;
      this.offsetX = 0;
      this.offsetY = 0;

      this.init();
    }

    init() {
      this.updateScale();
      window.addEventListener('resize', () => this.updateScale());
      window.addEventListener('orientationchange', () => this.updateScale());
    }

    updateScale() {
      const windowWidth = window.innerWidth;
      const windowHeight = window.innerHeight;

      // Рассчитываем коэффициент масштабирования с сохранением пропорций 16:9
      const scaleX = windowWidth / VIRTUAL_WIDTH;
      const scaleY = windowHeight / VIRTUAL_HEIGHT;
      this.scale = Math.min(scaleX, scaleY);

      // Центрируем виртуальную сцену в окне
      this.offsetX = Math.round((windowWidth - VIRTUAL_WIDTH * this.scale) / 2);
      this.offsetY = Math.round((windowHeight - VIRTUAL_HEIGHT * this.scale) / 2);

      this.stage.style.width = `${VIRTUAL_WIDTH}px`;
      this.stage.style.height = `${VIRTUAL_HEIGHT}px`;
      this.stage.style.position = 'absolute';
      this.stage.style.left = `${this.offsetX}px`;
      this.stage.style.top = `${this.offsetY}px`;
      this.stage.style.transformOrigin = '0 0';
      this.stage.style.transform = `scale(${this.scale})`;

      // Сохраняем devicePixelRatio в атрибуте для возможной графики на canvas
      this.dpr = window.devicePixelRatio || 1;
      this.stage.setAttribute('data-scale', this.scale.toFixed(4));
      this.stage.setAttribute('data-dpr', this.dpr);
    }

    /**
     * Преобразование экранных координат (касания) в виртуальные координаты сцены
     */
    screenToStage(clientX, clientY) {
      return {
        x: (clientX - this.offsetX) / this.scale,
        y: (clientY - this.offsetY) / this.scale,
      };
    }
  }

  window.StageManager = StageManager;
})();
