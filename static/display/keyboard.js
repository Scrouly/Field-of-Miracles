/**
 * keyboard.js — Экранная русская клавиатура для мультиборда.
 *
 * Требования:
 *  - Минимальная тач-цель 64×64 px, отступы не менее 8 px (здесь 76×76 px и отступ 12 px);
 *  - Раскладка русская, «ё» присутствует и приравнивается к «е»;
 *  - Защита от двойного тапа и ложных касаний ладонью (блокировка кнопки при первом нажатии);
 *  - Подсветка отгаданных букв (попадание / промах).
 */

(function () {
  'use strict';

  // 3 ряда русской клавиатуры
  const KEYBOARD_ROWS = [
    ['Ё', 'Й', 'Ц', 'У', 'К', 'Е', 'Н', 'Г', 'Ш', 'Щ', 'З', 'Х', 'Ъ'],
    ['Ф', 'Ы', 'В', 'А', 'П', 'Р', 'О', 'Л', 'Д', 'Ж', 'Э'],
    ['Я', 'Ч', 'С', 'М', 'И', 'Т', 'Ь', 'Б', 'Ю'],
  ];

  class KeyboardManager {
    constructor(containerElement, onKeyPress) {
      this.container = containerElement;
      this.onKeyPress = onKeyPress; // callback: function(letter)
      this.keyElements = new Map();
      this.isLocked = false;
      this.guessedLetters = new Set();
      this.targetWord = '';

      this.buildKeyboard();
    }

    buildKeyboard() {
      this.container.innerHTML = '';
      this.keyElements.clear();

      KEYBOARD_ROWS.forEach((rowLetters) => {
        const rowElem = document.createElement('div');
        rowElem.className = 'kb-row';

        rowLetters.forEach((letter) => {
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'kb-key';
          btn.textContent = letter;
          btn.setAttribute('data-letter', letter.toLowerCase());

          // Обработка касания/клика с защитой от двойного нажатия
          btn.addEventListener('pointerdown', (e) => {
            e.preventDefault();
            this.handleKeyClick(letter.toLowerCase(), btn);
          });

          this.keyElements.set(letter.toLowerCase(), btn);
          rowElem.appendChild(btn);
        });

        this.container.appendChild(rowElem);
      });
    }

    handleKeyClick(letter, btnElement) {
      // Защита от двойного нажатия и случайных касаний
      if (this.isLocked || btnElement.disabled || this.guessedLetters.has(letter)) {
        return;
      }

      // Блокируем кнопку немедленно
      this.lockKeyboard();
      btnElement.classList.add('key-active');

      if (typeof this.onKeyPress === 'function') {
        this.onKeyPress(letter)
          .catch((err) => {
            console.error('Action failed:', err);
          })
          .finally(() => {
            this.unlockKeyboard();
            btnElement.classList.remove('key-active');
          });
      } else {
        this.unlockKeyboard();
      }
    }

    lockKeyboard() {
      this.isLocked = true;
      this.container.classList.add('kb-locked');
    }

    unlockKeyboard() {
      this.isLocked = false;
      this.container.classList.remove('kb-locked');
    }

    /**
     * Обновление состояния клавиатуры из GameState.
     */
    update(guessedLettersArray, word, phase) {
      this.targetWord = (word || '').toLowerCase().replace(/ё/g, 'е');
      this.guessedLetters = new Set((guessedLettersArray || []).map((l) => l.toLowerCase()));

      const isAwaitLetter = phase === 'await_letter';

      this.keyElements.forEach((btn, letter) => {
        const normLetter = letter === 'ё' ? 'е' : letter;
        const isGuessed = this.guessedLetters.has(normLetter) || this.guessedLetters.has(letter);

        if (!isAwaitLetter) {
          // Если фаза не ожидания буквы — все кнопки заблокированы
          btn.disabled = true;
          return;
        }

        if (isGuessed) {
          btn.disabled = true;
          btn.classList.add('key-guessed');
          const isHit = this.targetWord.includes(normLetter);
          if (isHit) {
            btn.classList.add('key-hit');
          } else {
            btn.classList.add('key-miss');
          }
        } else {
          btn.disabled = false;
          btn.classList.remove('key-guessed', 'key-hit', 'key-miss');
        }
      });
    }
  }

  window.KeyboardManager = KeyboardManager;
})();
