/**
 * Essay result page — AI improved version panel.
 *
 * Behavior:
 *   - Collapsible accordion; lazy-fires the POST on first expand.
 *   - Spinner while the AI generates, inline error box with retry,
 *     side-by-side original vs improved text, copy-to-clipboard.
 *
 * Expected DOM (rendered by templates/essays/result.html):
 *   #improve-toggle-btn[data-url]  #improve-panel  #improve-chevron
 *   #improve-loading  #improve-error  #improve-error-text  #improve-retry-btn
 *   #improve-content  #improve-text  #improve-copy-btn  #improve-copy-label
 */
(function () {
    'use strict';

    function initDonutAndBars() {
        var donut = document.getElementById('donut-fg');
        if (donut) {
            var pct = parseFloat(donut.dataset.pct) || 0;
            var C = 326.7;
            donut.style.strokeDashoffset = C; // start empty
            setTimeout(function () {
                donut.style.strokeDashoffset = String(C * (1 - pct / 100));
                var cls = donut.getAttribute('class').replace('stroke-emerald-500', '');
                if (pct >= 80) donut.setAttribute('class', cls + ' stroke-emerald-500');
                else if (pct >= 60) donut.setAttribute('class', cls + ' stroke-teal-500');
                else if (pct >= 40) donut.setAttribute('class', cls + ' stroke-amber-500');
                else donut.setAttribute('class', cls + ' stroke-rose-500');
            }, 120);
        }

        document.querySelectorAll('.crit-bar').forEach(function (bar, i) {
            setTimeout(function () { bar.style.width = bar.dataset.width + '%'; }, 150 + i * 45);
        });
    }

    function initImprovePanel() {
        var toggleBtn = document.getElementById('improve-toggle-btn');
        if (!toggleBtn) return; // section not rendered (ungraded submission)

        var panel = document.getElementById('improve-panel');
        var chevron = document.getElementById('improve-chevron');
        var loading = document.getElementById('improve-loading');
        var errorBox = document.getElementById('improve-error');
        var errorText = document.getElementById('improve-error-text');
        var content = document.getElementById('improve-content');
        var textEl = document.getElementById('improve-text');
        var copyBtn = document.getElementById('improve-copy-btn');
        var copyLabel = document.getElementById('improve-copy-label');
        var retryBtn = document.getElementById('improve-retry-btn');
        var improveUrl = toggleBtn.dataset.url;

        var fetched = false;

        function show(el) { el.classList.remove('hidden'); }
        function hide(el) { el.classList.add('hidden'); }

        function showError(msg) {
            hide(loading);
            hide(content);
            errorText.textContent = msg;
            show(errorBox);
        }

        function getCsrfToken() {
            var input = document.querySelector('[name=csrfmiddlewaretoken]');
            if (input) return input.value;
            var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
            return m ? decodeURIComponent(m[1]) : '';
        }

        function fetchImproved() {
            hide(errorBox);
            show(loading);
            fetch(improveUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest',
                },
            })
                .then(function (res) {
                    return res.json().catch(function () { return {}; })
                        .then(function (data) {
                            if (!res.ok || !data.ok) {
                                throw new Error(data.error || 'Server xatosi. Qayta urinib ko\'ring.');
                            }
                            return data;
                        });
                })
                .then(function (data) {
                    textEl.textContent = data.content;
                    hide(loading);
                    show(content);
                    fetched = true;
                })
                .catch(function (err) { showError(err.message || 'Kutilmagan xatolik.'); });
        }

        toggleBtn.addEventListener('click', function () {
            var isHidden = panel.classList.toggle('hidden');
            chevron.style.transform = isHidden ? '' : 'rotate(180deg)';
            if (!isHidden && !fetched) fetchImproved();
        });

        if (retryBtn) retryBtn.addEventListener('click', fetchImproved);

        if (copyBtn) {
            copyBtn.addEventListener('click', function () {
                navigator.clipboard.writeText(textEl.textContent).then(function () {
                    copyLabel.textContent = '✓ Nusxalandi';
                    setTimeout(function () { copyLabel.textContent = 'Nusxalash'; }, 2000);
                });
            });
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        initDonutAndBars();
        initImprovePanel();
    });
})();
