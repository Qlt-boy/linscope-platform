/* ============ 林鉴知微平台 | LinScopePlatform · 应用逻辑 ============
 *
 * 原型（WorkBuddy 设计稿）的页面结构、组件与样式原样保留；本文件只把「取数」
 * 从写死的 window.* 常量改成向后端 FastAPI 取数（后端读本平台本地采集库）。
 * 每个页面 = load()（取数） + render(data)（渲染原型的 DOM 结构） + bind()（交互）。
 */
(function () {
  'use strict';

  /* ---------- 图标库 ---------- */
  var ICONS = {
    gauge: '<path d="M12 13.5l3-3"/><path d="M3.6 18a9 9 0 1 1 16.8 0"/><circle cx="12" cy="13.5" r="1"/>',
    server: '<rect x="3" y="4" width="18" height="7" rx="2"/><rect x="3" y="13" width="18" height="7" rx="2"/><path d="M7 7.5h.01M7 16.5h.01"/><path d="M11 7.5h6M11 16.5h6"/>',
    cpu: '<rect x="7" y="7" width="10" height="10" rx="2"/><path d="M10 2v3M14 2v3M10 19v3M14 19v3M2 10h3M2 14h3M19 10h3M19 14h3"/><rect x="10" y="10" width="4" height="4" rx="1"/>',
    network: '<rect x="9" y="3" width="6" height="4" rx="1"/><rect x="3" y="17" width="6" height="4" rx="1"/><rect x="15" y="17" width="6" height="4" rx="1"/><path d="M12 7v5M12 12H6v5M12 12h6v5"/>',
    monitor: '<rect x="2.5" y="3.5" width="19" height="13" rx="2"/><path d="M11.5 3.5v13"/><path d="M8 20h8M12 16.5V20"/>',
    archive: '<rect x="3" y="4" width="18" height="5" rx="2"/><path d="M5 9v9a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V9"/><path d="M10 13h4"/>',
    database: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
    file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h4"/>',
    users: '<circle cx="9" cy="8" r="3.2"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 5.2a3.2 3.2 0 0 1 0 5.6"/><path d="M17.6 14.4A6.5 6.5 0 0 1 21.5 20"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M2 12h3M19 12h3M4.9 19.1l2.1-2.1M17 7l2.1-2.1"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.6-3.6"/>',
    close: '<path d="M18 6L6 18M6 6l12 12"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    chevron: '<path d="M6 9l6 6 6-6"/>',
    lock: '<rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
    alert: '<circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16.5h.01"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    moon: '<path d="M20.5 14.8A8.7 8.7 0 0 1 9.2 3.5a8.7 8.7 0 1 0 11.3 11.3z"/>',
    menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
    check: '<path d="M4.5 12.5l5 5 10-11"/>',
    logout: '<path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3"/><path d="M10 17l-5-5 5-5"/><path d="M5 12h10"/>',
    refresh: '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 5v6h-6"/>',
    terminal: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9l3 3-3 3M13 15h4"/>',
    download: '<path d="M12 4v11"/><path d="M7.5 10.5L12 15l4.5-4.5"/><path d="M5 19h14"/>'
  };

  function icon(name, size) {
    var s = size || 18;
    return '<svg viewBox="0 0 24 24" width="' + s + '" height="' + s + '" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' + (ICONS[name] || '') + '</svg>';
  }

  function esc(s) {
    return String(s === null || s === undefined ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  /* ---------- 通用组件（沿用原型） ---------- */
  function cardHead(title, sub, right) {
    return '<div class="card-head"><div class="t"><div class="title">' + title + '</div>' +
      (sub ? '<div class="sub">' + sub + '</div>' : '') + '</div>' + (right || '') + '</div>';
  }
  function moduleTabs(items, active, dataAttr, extra) {
    return '<div class="page-module-tabs" role="tablist">' +
      '<div class="page-module-tab-list">' + (items || []).map(function (item) {
        var on = item.key === active;
        return '<button type="button" role="tab" aria-selected="' + (on ? 'true' : 'false') + '"' +
          ' class="page-module-tab' + (on ? ' active' : '') + '" data-' + dataAttr + '="' + esc(item.key) + '">' +
          '<span class="ico">' + icon(item.icon || 'folder', 15) + '</span>' +
          '<span class="txt">' + esc(item.label) + '</span>' +
          (item.count === undefined || item.count === null ? '' : '<b>' + esc(item.count) + '</b>') +
          '</button>';
      }).join('') + '</div>' +
      (extra ? '<div class="page-module-extra">' + extra + '</div>' : '') + '</div>';
  }

  function clientPage(items, state, pageKey, sizeKey, sizes, defaultSize) {
    var allowed = sizes || [10, 20, 50];
    var size = Number(state[sizeKey] || defaultSize || allowed[0]) || allowed[0];
    if (allowed.indexOf(size) < 0) size = allowed[0];
    var source = items || [];
    var total = source.length;
    var pages = Math.max(1, Math.ceil(total / size));
    var page = Math.max(1, Math.min(Number(state[pageKey] || 1) || 1, pages));
    state[sizeKey] = size;
    state[pageKey] = page;
    var start = (page - 1) * size;
    return { rows: source.slice(start, start + size), total: total, page: page, pages: pages, size: size, start: start };
  }

  function sizeSelect(id, size, sizes) {
    return '<select class="grid-filter-select module-page-size" id="' + esc(id) + '">' +
      (sizes || [10, 20, 50]).map(function (n) {
        return '<option value="' + n + '"' + (Number(size) === Number(n) ? ' selected' : '') + '>' + n + ' 条/页</option>';
      }).join('') + '</select>';
  }

  function pagerFooter(prefix, view, unit) {
    var label = unit || '条';
    return '<div class="footer-bar module-pager">' +
      '<span class="kpi-trend" id="' + esc(prefix) + 'FooterCount">共 ' + esc(view.total) + ' ' + esc(label) + ' · 第 ' + esc(view.page) + ' / ' + esc(view.pages) + ' 页</span>' +
      '<div class="btn-group module-pager-controls">' +
      sizeSelect(prefix + 'Size', view.size, [10, 20, 50]) +
      '<button class="btn btn-ghost xs" id="' + esc(prefix) + 'Prev"' + (view.page <= 1 ? ' disabled' : '') + '>上一页</button>' +
      '<span class="module-page-number" id="' + esc(prefix) + 'PageNo">' + esc(view.page) + ' <em>/ ' + esc(view.pages) + '</em></span>' +
      '<button class="btn btn-ghost xs" id="' + esc(prefix) + 'Next"' + (view.page >= view.pages ? ' disabled' : '') + '>下一页</button>' +
      '</div></div>';
  }

  function bindClientPager(prefix, state, pageKey, sizeKey, rerender) {
    var size = document.getElementById(prefix + 'Size');
    if (size) size.addEventListener('change', function () {
      state[sizeKey] = Number(size.value) || 10;
      state[pageKey] = 1;
      rerender();
    });
    var prev = document.getElementById(prefix + 'Prev');
    if (prev) prev.addEventListener('click', function () {
      if (Number(state[pageKey]) > 1) { state[pageKey] = Number(state[pageKey]) - 1; rerender(); }
    });
    var next = document.getElementById(prefix + 'Next');
    if (next) next.addEventListener('click', function () {
      state[pageKey] = Number(state[pageKey] || 1) + 1;
      rerender();
    });
  }

  function bindModuleTabs(attribute, onSelect) {
    Array.prototype.forEach.call(document.querySelectorAll('[data-' + attribute + ']'), function (node) {
      node.addEventListener('click', function () {
        onSelect(node.getAttribute('data-' + attribute));
      });
    });
  }

  function refreshPageHash(pageKey, query) {
    var hash = '#/' + pageKey + (query ? '?' + query : '');
    if (location.hash === hash) route(); else location.hash = hash;
  }

  function tag(text, tone) {
    return '<span class="tag ' + (tone || 'neutral') + '">' +
      (tone === 'success' ? '<i class="dot"></i>' : '') + esc(text) + '</span>';
  }

  function table(cols, rows) {
    var head = '<tr>' + cols.map(function (c) {
      var w = c.width ? ' style="width:' + c.width + 'px"' : '';
      return '<th' + w + '>' + (c.html || esc(c.text)) + '</th>';
    }).join('') + '</tr>';
    if (cols.some(function (c) { return c.filterHtml; })) {
      head += '<tr class="grid-filter-row">' + cols.map(function (c) {
        var w = c.width ? ' style="width:' + c.width + 'px"' : '';
        return '<th' + w + '>' + (c.filterHtml || '') + '</th>';
      }).join('') + '</tr>';
    }
    var body = rows.map(function (r) {
      var rowAttr = r.rowAttr ? ' ' + r.rowAttr : '';
      return '<tr' + rowAttr + '>' + r.map(function (cell) {
        var cls = cell.cls ? ' class="' + cell.cls + '"' : '';
        return '<td' + cls + '>' + (cell.html || esc(cell.text)) + '</td>';
      }).join('') + '</tr>';
    }).join('');
    return '<table class="grid"><thead>' + head + '</thead><tbody>' + body + '</tbody></table>';
  }

  function emptyTable(cols, message) {
    return table(cols, []).replace('<tbody></tbody>', '<tbody><tr><td class="empty-table" colspan="' + cols.length + '">' + esc(message) + '</td></tr></tbody>');
  }

  function statList(items) {
    return '<div class="stat-list">' + items.map(function (i) {
      return '<div class="stat-item"><span class="n">' + esc(i.name) + '</span><span class="v">' + esc(i.value) + '</span></div>';
    }).join('') + '</div>';
  }

  function kpiCards(list, small, className) {
    if (small) return '<div class="metric-strip" role="group" aria-label="统计摘要">' + list.map(function (k) {
      return '<div class="metric-item" title="' + esc(k.note || k.trend || '') + '">' +
        '<span>' + esc(k.label) + '</span><b>' + esc(k.value) + '</b><small>' + esc(k.unit || '') + '</small></div>';
    }).join('') + '</div>';
    return '<div class="kpi-row ' + (className || '') + '">' + list.map(function (k) {
      return '<div class="kpi-card">' +
        '<div class="kpi-label">' + esc(k.label) + '</div>' +
        '<div class="kpi-value-row"><span class="kpi-value' + (small ? ' sm' : '') + '">' + esc(k.value) + '</span>' +
        '<span class="kpi-unit">' + esc(k.unit || '') + '</span></div>' +
        '<div class="kpi-trend ' + (k.tone === 'success' ? 'success' : k.tone === 'warning' ? 'warning' : '') + '">' + esc(k.note || k.trend || '') + '</div>' +
        '</div>';
    }).join('') + '</div>';
  }

  function select(text) {
    return '<div class="input"><span class="val">' + esc(text) + '</span>' + icon('chevron', 14) + '</div>';
  }
  function input(text, mono) {
    return '<div class="input"><span class="val' + (mono ? ' mono' : '') + '">' + esc(text) + '</span></div>';
  }
  function lockedInput(text) {
    return '<div class="input muted"><span class="val mono">' + esc(text) + '</span>' + icon('lock', 14) + '</div>';
  }
  
  function toggleRow(title, desc, on) {
    return '<div class="toggle-row"><div class="meta"><span class="t">' + esc(title) + '</span><span class="d">' + esc(desc) + '</span></div>' +
      '<button class="switch ' + (on ? 'on' : 'off') + '" data-toggle="1" aria-pressed="' + (on ? 'true' : 'false') + '"><span class="knob"></span></button></div>';
  }

  /* ---------- 交互控件：在原型 .input 外壳里放真控件（不改 CSS） ---------- */
  var CTRL = 'flex:1;min-width:0;border:0;background:transparent;font:inherit;color:inherit;outline:none';

  /* ---------- 下拉选择器（自绘：深浅色都看得清，带计数与勾选） ---------- */
  var OPEN_SELECT = null;          // 当前展开的下拉 id
  var SELECT_INDEX = 0;

  function picker(id, options, value, placeholder) {
    var list = (options || []).map(function (opt) {
      var v = opt && opt.value !== undefined ? opt.value : opt;
      var label = opt && opt.label !== undefined ? opt.label : opt;
      return { value: v, label: label, count: opt ? opt.count : undefined };
    });
    if (placeholder) list = [{ value: '', label: placeholder }].concat(list);
    if (!list.length) list = [{ value: '', label: '暂无可选项' }];
    var selected = null;
    for (var i = 0; i < list.length; i++) {
      if (String(list[i].value) === String(value === undefined || value === null ? '' : value)) { selected = list[i]; break; }
    }
    if (!selected) selected = list[0] || { value: '', label: '' };
    var native = '<select id="' + id + '" class="na-native">' + list.map(function (opt) {
      return '<option value="' + esc(opt.value) + '"' +
        (String(opt.value) === String(selected.value) ? ' selected' : '') + '>' + esc(opt.label) + '</option>';
    }).join('') + '</select>';
    return '<div class="na-select" id="' + id + 'Wrap" data-select="' + id + '">' +
      '<button type="button" class="input na-trigger" data-open="' + id + '" aria-haspopup="listbox" aria-expanded="false">' +
      '<span class="val' + (selected.value === '' ? ' ph' : '') + '" id="' + id + 'Label">' + esc(selected.label) + '</span>' +
      icon('chevron', 14) + '</button>' + native + '</div>';
  }

  function selectOptions(id) {
    var node = document.getElementById(id);
    if (!node) return [];
    return Array.prototype.map.call(node.options, function (opt) {
      return { value: opt.value, label: opt.textContent, count: opt.getAttribute('data-count') };
    });
  }

  function openSelect(id) {
    closeSelect();
    var trigger = document.querySelector('[data-open="' + id + '"]');
    var node = document.getElementById(id);
    if (!trigger || !node) return;
    var current = node.value;
    var options = selectOptions(id);
    SELECT_INDEX = Math.max(0, options.map(function (o) { return String(o.value); }).indexOf(String(current)));
    OPEN_SELECT = id;
    trigger.setAttribute('aria-expanded', 'true');

    var panel = document.createElement('div');
    panel.className = 'na-panel';
    panel.id = 'naPanel';
    panel.innerHTML = options.map(function (opt, index) {
      var sel = String(opt.value) === String(current);
      return '<div class="na-option' + (sel ? ' sel' : '') + (index === SELECT_INDEX ? ' active' : '') +
        '" data-value="' + esc(opt.value) + '" data-index="' + index + '">' +
        '<span class="t">' + esc(opt.label) + '</span>' +
        (opt.count !== undefined && opt.count !== null && opt.count !== ''
          ? '<span class="c">' + esc(opt.count) + '</span>' : '') +
        '<span class="tick">' + icon('check', 12) + '</span></div>';
    }).join('');
    document.body.appendChild(panel);
    positionSelectPanel();
    Array.prototype.forEach.call(panel.querySelectorAll('.na-option'), function (row) {
      row.addEventListener('mousedown', function (event) {
        event.preventDefault();
        chooseSelect(id, row.getAttribute('data-value'));
      });
    });
    var active = panel.querySelectorAll('.na-option')[SELECT_INDEX];
    if (active && active.scrollIntoView) active.scrollIntoView({ block: 'nearest' });
  }

  /** 把面板贴到触发器下方（空间不够就翻到上方）；触发器不可见时返回 false */
  function positionSelectPanel() {
    var panel = document.getElementById('naPanel');
    if (!panel || !OPEN_SELECT) return false;
    var trigger = document.querySelector('[data-open="' + OPEN_SELECT + '"]');
    if (!trigger || !trigger.isConnected) return false;
    var rect = trigger.getBoundingClientRect();
    if (rect.bottom < 0 || rect.top > window.innerHeight) return false;
    var width = Math.max(rect.width, 180);
    panel.style.minWidth = width + 'px';
    panel.style.left = Math.max(8, Math.min(rect.left, window.innerWidth - width - 12)) + 'px';
    var panelHeight = Math.min(panel.scrollHeight + 12, window.innerHeight - 24);
    var spaceBelow = window.innerHeight - rect.bottom - 8;
    if (spaceBelow < Math.min(260, panelHeight) && rect.top > spaceBelow) {
      panel.style.top = '';
      panel.style.bottom = (window.innerHeight - rect.top + 6) + 'px';
    } else {
      panel.style.bottom = '';
      panel.style.top = (rect.bottom + 6) + 'px';
    }
    return true;
  }

  function chooseSelect(id, value) {
    var node = document.getElementById(id);
    if (!node) { closeSelect(); return; }
    if (String(node.value) !== String(value)) {
      node.value = value;
      var label = document.getElementById(id + 'Label');
      var opt = node.options[node.selectedIndex];
      if (label && opt) {
        label.textContent = opt.textContent;
        label.className = 'val' + (String(value) === '' ? ' ph' : '');
      }
      // 触发原有 change 绑定（各页面的查询/联动逻辑照旧生效）
      node.dispatchEvent(new Event('change', { bubbles: true }));
    }
    closeSelect();
  }

  function closeSelect() {
    var panel = document.getElementById('naPanel');
    if (panel) panel.remove();
    var trigger = OPEN_SELECT ? document.querySelector('[data-open="' + OPEN_SELECT + '"]') : null;
    if (trigger) trigger.setAttribute('aria-expanded', 'false');
    OPEN_SELECT = null;
  }

  function moveSelect(step) {
    if (!OPEN_SELECT) return;
    var options = selectOptions(OPEN_SELECT);
    if (!options.length) return;
    SELECT_INDEX = Math.max(0, Math.min(options.length - 1, SELECT_INDEX + step));
    var panel = document.getElementById('naPanel');
    if (!panel) return;
    var rows = panel.querySelectorAll('.na-option');
    Array.prototype.forEach.call(rows, function (row, index) {
      row.classList.toggle('active', index === SELECT_INDEX);
    });
    if (rows[SELECT_INDEX] && rows[SELECT_INDEX].scrollIntoView) {
      rows[SELECT_INDEX].scrollIntoView({ block: 'nearest' });
    }
  }

  /* ---------- 弹窗关闭：统一机制（点 × / 点取消 / 点遮罩 / Esc 都真正生效） ---------- */
  var OVERLAY_DISMISS = null;      // 需要回执的弹窗（如远程命令确认）在这里挂回调

  function dismissOverlay() {
    var hook = OVERLAY_DISMISS;
    OVERLAY_DISMISS = null;
    clearTimeout(OVERLAY_GUARD);
    if (overlayIsOpen()) {
      if (typeof hook === 'function') { try { hook(); } catch (e) {} }
      if (overlayIsOpen()) closeOverlay();
    } else if (typeof hook === 'function') {
      try { hook(); } catch (e) {}
    }
    if (STATE.refreshAfterOverlay) {          // 弹窗期间改过数据：关窗时补一次列表刷新
      STATE.refreshAfterOverlay = false;
      route();
    }
  }

  function overlayIsOpen() {
    return !!document.getElementById('overlay');
  }

  var OVERLAY_GUARD = null;

  
  function textBox(id, value, placeholder) {
    return '<div class="input"><input id="' + id + '" type="text" value="' + esc(value || '') +
      '" placeholder="' + esc(placeholder || '') + '" style="' + CTRL + '"/>' + icon('search', 14) + '</div>';
  }

  function plainBox(id, value, type) {
    return '<div class="input"><input id="' + id + '" type="' + (type || 'text') + '" value="' + esc(value || '') +
      '" style="' + CTRL + '"/></div>';
  }

  function field(label, control) {
    return '<div class="field"><label>' + esc(label) + '</label>' + control + '</div>';
  }

  /* ---------- 运行时状态 ---------- */
  var STATE = {
    status: null,          // /api/system/status
    meta: null,            // /api/system/meta
    days: 7,               // 总览统计区间
    resourceMode: 'trend', // 资源图：trend（曲线）/ devices（按设备）
    devices: { page: 1, page_size: 10, keyword: '', type: 'all', status: 'all',
               vendor: 'all', group: 'all', region: 'all', online: 'all',
               name: '', role: '', model: '', version: '', ip: '', owner: '', location: '',
               asset_no: '', usage: '', warranty_until: '', note: '',
               sort: 'ip', order: 'asc' },
    deviceSelected: {},
    pending: { page: 1, page_size: 10, keyword: '', sort: 'ip', order: 'asc', tab: 'pending' },
    pendingSelected: {},
    lastRenderedPage: '',
    overviewTab: 'health', overviewInspectPage: 1, overviewInspectSize: 10,
    backup: { keyword: '', page: 1, page_size: 20, tab: 'files', coverage_page: 1, coverage_size: 10 },
    alerts: { hours: 168, severity: '', status: '', keyword: '', device: '', limit: 500, page: 1, page_size: 10, tab: 'list' },
    reports: { keyword: '', kind: 'all', fmt: 'all', page: 1, page_size: 20, tab: 'archive' },
    audit: { username: '', action: 'all', keyword: '', hours: 168, op_page: 1, op_size: 10 },
    switchTab: 'checks', serverTab: 'checks', usersTab: 'accounts', settingsTab: 'platform',
    remote: { ip: '', category: 'switch', tab: 'terminal', device_page: 1, device_size: 10, session_page: 1, session_size: 10 }, remoteDevices: [], remotePolicy: {}, remoteSessions: {},
    collectFilter: { ip: '', only_failed: 0, limit: 500, run_id: 0 }, collectDevices: [], collect: {},
    collectUi: { tab: 'devices', device_page: 1, device_size: 10, runs_page: 1, runs_size: 10,
                 logs_page: 1, logs_size: 20, changes_page: 1, changes_size: 10,
                 missing_page: 1, missing_size: 10 },
    collectSelected: {}, collectWithConfig: false,
    collectPickFilter: { group: 'all', result: 'all' }, collectPrecheck: null,
    user: null, perms: {}, overview: {}, authReady: false, authStatus: null,
    nextHash: '', lastUser: localStorage.getItem('ni-last-user') || '',
    refreshAfterOverlay: false,
    lastError: null,
    deviceViewGeneration: 0,
    deviceDeletedIps: {},
    deviceRefreshTimer: null,
    navOpenGroup: '', navOpenSection: '', navActivePage: '',
    wallCategory: 'switch', wallDevice: '', wallFace: 'front', wallAuto: false, wall3d: null, wallHwObserver: null
  };

  /* ---------- 页面状态 ↔ URL 查询串（刷新/转发链接也能带着筛选条件） ---------- */
  function syncStateFromQuery(key, query) {
    if (key === 'overview') applyOverviewQuery(query);
    else if (key === 'pending') applyPendingQuery(query);
    else if (key === 'devices') applyDevicesQuery(query);
    else if (key === 'backup') applyBackupQuery(query);
    else if (key === 'alerts') applyAlertsQuery(query);
    else if (key === 'reports') applyReportsQuery(query);
    else if (key === 'users') applyAuditQuery(query);
    else if (key === 'server') STATE.serverTab = ['checks','resources','environment','channels','advice'].indexOf(query.tab) >= 0 ? query.tab : 'checks';
    else if (key === 'switch' || key === 'security') STATE.switchTab = (key === 'security' ? ['checks','perf','advice'] : ['checks','lldp','perf','advice']).indexOf(query.tab) >= 0 ? query.tab : 'checks';
    else if (key === 'remote' || key === 'console') remoteApplyQuery(query);
  }

  /* ---------- 数据源角标 / 提示条 / 骨架 ---------- */
  function sourceBadge() {
    return '<span class="js-source-badge"></span>';
  }

  function paintSourceBadges() {
    var nodes = document.querySelectorAll('.js-source-badge');
    if (!nodes.length) return;
    var status = STATE.status;
    var counts = (status && status.counts) || {};
    var html = !status
      ? '<span class="chip">本地采集库：读取中…</span>'
      : '<span class="chip success" title="设备 ' + esc(counts.devices || 0) +
        ' 台 · 巡检 ' + esc(counts.inspections || 0) + ' 条">数据源：本平台自带采集</span>';
    Array.prototype.forEach.call(nodes, function (node) { node.innerHTML = html; });
  }

  function notice(text, tone) {
    return '<div class="notice" style="' + (tone === 'danger' ? 'background:var(--danger-soft-bg);color:var(--danger-text)' : '') + '">' +
      icon('alert', 14) + '<span>' + esc(text) + '</span></div>';
  }

  function sourceNotice(info, source) {
    // 纯本地采集没有「外部数据源不可达」这回事；保留空实现，页面调用不用改。
    return '';
  }

  function loadingView(title) {
    return '<div class="page-head"><div class="page-title"><h1>' + esc(title) + '</h1></div></div>' +
      '<div class="loading-state" role="status" aria-live="polite">正在加载，请稍候…</div>';
  }

  function errorView(err, retryLabel) {
    return '<section class="card error-state" role="alert"><h2>' + (err && err.status === 403 ? '当前账号无权查看此内容' : '暂时无法加载当前内容') +
      '</h2><p>请确认网络和服务状态后重试。</p><button type="button" class="btn btn-primary sm" id="retryLoad">' +
      esc(retryLabel || '重新加载') + '</button><details><summary>错误详情</summary><p>' + esc(err && err.message || '未知错误') + '</p></details></section>';
  }

  /* ---------- 侧边导航 ---------- */
  function navPathFor(active) {
    var found = null;
    NAV.forEach(function (domain) {
      if (found) return;
      var direct = (domain.items || []).filter(function (it) { return it.key === active; })[0];
      if (direct) { found = { domain: domain, section: null, item: direct }; return; }
      (domain.sections || []).forEach(function (section) {
        if (found) return;
        var item = (section.items || []).filter(function (it) { return it.key === active; })[0];
        if (item) found = { domain: domain, section: section, item: item };
      });
    });
    return found;
  }

  

  function renderNav(active) {
    var brand = siteParts();
    return '<a class="brand" href="#/overview" aria-label="返回巡检总览"><div class="brand-logo">' + icon('gauge', 18) + '</div>' +
      '<div class="brand-text"><span class="brand-name" title="' + esc(brand.full) + '">' + esc(brand.name) + '</span>' +
      '<span class="brand-sub">' + esc(brand.sub) + '</span></div></a>' +
      '<nav class="workspace-nav" aria-label="主导航">' + NAV.map(function (domain) {
        return '<section class="workspace-nav-group"><h2>' + esc(domain.group) + '</h2>' +
          (domain.items || []).map(function (item) {
            return '<a class="nav-item' + (item.key === active ? ' active' : '') + '" href="#/' + item.key + '"' +
              (item.key === active ? ' aria-current="page"' : '') + '><span class="ico">' + icon(item.icon,15) +
              '</span><span class="txt">' + esc(item.label) + '</span></a>';
          }).join('') + '</section>';
      }).join('') + '</nav><div class="side-spacer"></div>' + userCardHtml();
  }

  /* Related pages carry an explicit device identity, never an ambiguous keyword. */
  function workflowContext(key, query, data) {
    var health = ['switch', 'server', 'security'].indexOf(key) >= 0;
    var device = health ? ((data || {}).device || {}).ip || query.device : query.device || query.ip || query.scope_device;
    var category = health ? key : query.category || query.type || query.kind;
    if (['switch', 'server', 'security'].indexOf(category) < 0) category = '';
    return { device: String(device || ''), category: category };
  }

  function workflowHref(target, context) {
    var q = [];
    var device = context.device;
    if (target === 'pending') q.push('tab=logs');
    if (target === 'reports') q.push('tab=archive');
    if (target === 'backup') q.push('tab=files');
    if (device) {
      var field = target === 'devices' || target === 'pending' ? 'ip' :
        target === 'backup' ? 'keyword' : 'device';
      q.push(field + '=' + encodeURIComponent(device));
    }
    if (device && target === 'backup') q.push('scope_device=' + encodeURIComponent(device));
    if (context.category) q.push('category=' + encodeURIComponent(context.category));
    if (target === 'alerts') q.push('status=', 'severity=', 'keyword=');
    if (target === 'reports') q.push('kind=all', 'fmt=all');
    // Make the URL the source of truth when returning to an unfiltered module.
    if (target === 'alerts' && !device) q.push('device=');
    return '#/' + target + (q.length ? '?' + q.join('&') : '');
  }

  function workflowNav(key, query, data) {
    if (['overview','pending','devices','switch','server','security','alerts','backup','reports'].indexOf(key) < 0) return '';
    var context = workflowContext(key, query, data);
    var healthKey = context.category || 'switch';
    var links = [
      {key:'pending',label:'采集日志'}, {key:'devices',label:'设备台账'},
      {key:'alerts',label:'告警处置'},
      {key:'reports',label:'报告归档'}, {key:'backup',label:'配置备份'}
    ];
    var healthLinks = context.category ? [{key:healthKey,label:'健康检查'}] : [{key:'switch',label:'交换机健康',family:true},{key:'server',label:'服务器健康',family:true},{key:'security',label:'安全设备健康',family:true}];
    links.splice.apply(links, [2,0].concat(healthLinks));
    return '<details class="workflow"><summary>关联模块' + icon('chevron',12) + '</summary><div class="related-menu">' +
      '<div class="workflow-context">' + (context.device ? '当前设备 <b class="mono">' + esc(context.device) + '</b>' : '前往相关模块') + '</div>' +
      '<nav class="workflow-stages" aria-label="关联模块">' + links.filter(function (item) { return item.key !== key; }).map(function (item) {
        var href = item.key === 'pending' && !context.device ? '#/pending' : workflowHref(item.key, item.family ? {device:''} : context);
        return '<a class="workflow-stage" href="' + esc(href) + '">' + esc(item.key === 'pending' && !context.device ? '设备采集' : item.label) + '</a>';
      }).join('') + '</nav></div></details>';
  }

  function mountWorkflow(main, key, query, data) {
    var markup = workflowNav(key, query, data);
    var host = main.querySelector('.topbar-right');
    if (markup && host) host.insertAdjacentHTML('afterbegin', markup);
  }

  function topbar(placeholder) {
    var navPath = navPathFor(key_href());
    var crumb = navPath
      ? '<span>' + esc(navPath.domain.group) + '</span><span class="crumb-sep">/</span>' +
        (navPath.section ? '<span>' + esc(navPath.section.group) + '</span><span class="crumb-sep">/</span>' : '') +
        '<span class="crumb-current">' + esc(navPath.item.label) + '</span>'
      : '';
    return '<div class="topbar"><button type="button" class="icon-btn mobile-nav-btn" id="mobileNavBtn" aria-label="打开导航" aria-controls="sidebar" aria-expanded="false">' + icon('menu', 18) + '</button>' +
      '<span class="crumb">' + crumb + '</span>' +
      '<div class="topbar-right"><a class="workspace-search" href="#/search">' + icon('search',16) + '<span>全局检索</span></a>' + sourceBadge() +
      '<button class="icon-btn" id="themeBtn" title="切换主题"></button>' +
      '</div></div>';
  }

  /* ---------- 顶栏全局搜索（设备 / 告警 / 备份 一次搜，回车可跳到设备清单） ---------- */
  var SEARCH_TIMER = null;

  function bindGlobalSearch() {
    var box = document.getElementById('globalSearch');
    if (!box || box.dataset.bound === '1') return;
    box.dataset.bound = '1';
    box.addEventListener('input', function () {
      var kw = box.value.trim();
      if (SEARCH_TIMER) clearTimeout(SEARCH_TIMER);
      if (!kw) { closeSearchPanel(); return; }
      SEARCH_TIMER = setTimeout(function () { runSearch(kw); }, 220);
    });
    box.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        var kw = box.value.trim();
        if (kw) {
          closeSearchPanel();
          STATE.devices.keyword = kw;
          STATE.devices.page = 1;
          location.hash = '#/devices?keyword=' + encodeURIComponent(kw);
          if (key_href() === 'devices') route();
        }
      } else if (e.key === 'Escape') {
        closeSearchPanel();
      }
    });
    box.addEventListener('blur', function () {
      setTimeout(closeSearchPanel, 180);          // 让点击结果先落地
    });
  }

  function key_href() {
    return (location.hash || '').replace(/^#\/?/, '').split('?')[0] || 'overview';
  }

  function closeSearchPanel() {
    var panel = document.getElementById('searchPanel');
    if (panel) panel.remove();
  }

  function runSearch(keyword) {
    window.NetInspect.search(keyword).then(function (data) {
      var currentSearch = document.getElementById('globalSearch');
      if (!currentSearch || currentSearch.value.trim() !== keyword) return;
      var box = document.getElementById('searchBox');
      if (!box) return;
      closeSearchPanel();
      var panel = document.createElement('div');
      panel.id = 'searchPanel';
      panel.style.cssText = 'position:absolute;top:52px;right:0;width:560px;z-index:40;background:var(--surface);border:1px solid var(--border);border-radius:var(--r-card);padding:16px;box-shadow:0 12px 32px rgba(0,0,0,.14)';
      panel.innerHTML = searchPanelHtml(data);
      box.appendChild(panel);
      Array.prototype.forEach.call(panel.querySelectorAll('[data-goto]'), function (node) {
        node.addEventListener('mousedown', function (e) {
          e.preventDefault();
          goto(node.getAttribute('data-goto'));
          closeSearchPanel();
        });
      });
    }).catch(function (err) { showToast('搜索失败：' + err.message); });
  }

  function searchPanelHtml(data) {
    var total = data.total || 0;
    if (!total) {
      return '<div class="card-head"><div class="t"><div class="title">未找到「' + esc(data.keyword) + '」</div>' +
        '<div class="sub">试试设备名 / IP / 型号 / 责任人 / 资产编号 / 告警关键字</div></div></div>';
    }
    var html = '<div class="card-head" style="margin-bottom:10px"><div class="t">' +
      '<div class="title">搜索「' + esc(data.keyword) + '」</div>' +
      '<div class="sub">设备 ' + (data.devices || []).length + ' · 告警 ' + (data.alerts || []).length +
      ' · 备份 ' + (data.backups || []).length + ' ｜ 数据源：' + esc(sourceLabelOf(data.source)) + '</div></div>' +
      '<span class="kpi-trend">回车查看完整设备清单</span></div>';

    if ((data.devices || []).length) {
      html += '<div style="font-size:12px;color:var(--text-3);margin:8px 0 4px">设备</div><div class="stat-list">';
      data.devices.forEach(function (d) {
        var healthPage = d.group_kind === 'server' ? 'server' : (d.group_kind === 'security' ? 'security' : 'switch');
        html += '<div class="stat-item" data-goto="#/' + healthPage +
          '?device=' + encodeURIComponent(d.id) + '" style="cursor:pointer;height:auto;padding:8px 0;gap:8px">' +
          '<span class="n" style="color:var(--text-1)">' + esc(d.name) + '</span>' +
          '<span class="v">' + esc(d.ip) + '</span>' +
          '<span class="kpi-trend">' + esc(d.type_label) + ' · ' + esc(d.model) + '</span>' +
          '<span class="status-text ' + toneClass(d.health_tone) + '">' + esc(d.health_label) + '</span></div>';
      });
      html += '</div>';
    }
    if ((data.alerts || []).length) {
      html += '<div style="font-size:12px;color:var(--text-3);margin:10px 0 4px">告警</div><div class="stat-list">';
      data.alerts.forEach(function (a) {
        html += '<div class="stat-item" data-goto="#/reports" style="cursor:pointer;height:auto;padding:8px 0;gap:8px">' +
          '<span class="n" style="color:var(--text-1);white-space:normal">' + esc(a.title) + '</span>' +
          '<span class="kpi-trend">' + esc(a.severity_label) + ' · ' + esc(a.device) + ' · ' + esc(a.time) + '</span></div>';
      });
      html += '</div>';
    }
    if ((data.backups || []).length) {
      html += '<div style="font-size:12px;color:var(--text-3);margin:10px 0 4px">备份</div><div class="stat-list">';
      data.backups.forEach(function (b) {
        html += '<div class="stat-item" data-goto="#/backup?keyword=' + encodeURIComponent(b.device_ip) +
          '" style="cursor:pointer;height:auto;padding:8px 0;gap:8px">' +
          '<span class="n mono" style="color:var(--text-1)">' + esc(b.name) + '</span>' +
          '<span class="kpi-trend">' + esc(b.device_ip) + ' · ' + esc(b.size_text) + ' · ' + esc(b.time) + '</span></div>';
      });
      html += '</div>';
    }
    return html;
  }

  function goto(hash) {
    if (!hash) return;
    if (location.hash === hash) { route(); return; }
    location.hash = hash;
  }

  function orgName() {
    var st = STATE.status || {};
    var live = (st.settings || {}).org_name;
    return live || (STATE.meta && STATE.meta.org_name) ||
      '林鉴知微技术服务股份有限公司 · 网络运维中心';
  }

  function siteName() {
    var st = STATE.status || {};
    var live = (st.settings || {}).site_name;
    return live || (STATE.meta && STATE.meta.site_name) ||
      '林鉴知微平台 | LinScopePlatform';
  }

  function siteParts() {
    var full = String(siteName() || '').trim() || '林鉴知微平台 | LinScopePlatform';
    var pieces = full.split(/[|｜]/);
    var name = (pieces.shift() || full).trim();
    var sub = pieces.join('|').trim() || 'LinScopePlatform';
    return { full: full, name: name, sub: sub };
  }

  /* ---------- 折线图（沿用原型的自绘 SVG） ---------- */
  function lineChart(opts) {
    var labels = opts.labels || [];
    var series = (opts.series || []).filter(function (s) { return s && s.values; });
    var flat = [];
    series.forEach(function (s) {
      s.values.forEach(function (v) { if (v !== null && v !== undefined && !isNaN(v)) flat.push(Number(v)); });
    });
    if (!labels.length || !flat.length) {
      return '<div class="notice">' + esc(opts.empty || '该区间暂无数据') + '</div>';
    }
    var dataMin = Math.min.apply(null, flat), dataMax = Math.max.apply(null, flat);
    var ticks = (opts.yTicks || []).map(Number).filter(function (v) { return isFinite(v); });
    if (!ticks.length || dataMin < Math.min.apply(null, ticks) || dataMax > Math.max.apply(null, ticks)) {
      ticks = niceTicks(dataMin, dataMax);
    }
    ticks.sort(function (a, b) { return b - a; });
    var yMax = ticks[0], yMin = ticks[ticks.length - 1];
    var W = 640, H = 230, PL = 34, PB = 24, PT = 10, PR = 8;
    var pw = W - PL - PR, ph = H - PT - PB;
    var span = Math.max(0.0001, yMax - yMin);
    var step = labels.length > 1 ? pw / (labels.length - 1) : 0;
    var x = function (i) { return PL + i * step; };
    var y = function (v) { return PT + Math.max(0, Math.min(1, (yMax - v) / span)) * ph; };

    var grid = ticks.map(function (v) {
      return '<line x1="' + PL + '" y1="' + y(v) + '" x2="' + (W - PR) + '" y2="' + y(v) + '" stroke="var(--chart-grid)" stroke-width="1"/>' +
        '<text x="0" y="' + (y(v) + 3.5) + '" font-size="10" font-family="var(--font-num)" fill="var(--text-3)">' + v + '</text>';
    }).join('');

    var every = labels.length > 8 ? Math.ceil(labels.length / 8) : 1;
    var xAxis = labels.map(function (l, i) {
      if (i % every !== 0 && i !== labels.length - 1) return '';
      return '<text x="' + x(i) + '" y="' + (H - 6) + '" font-size="11" font-family="var(--font-num)" fill="var(--text-3)" text-anchor="middle">' + esc(l) + '</text>';
    }).join('');

    var lines = series.map(function (s) {
      var runs = [], current = [];
      s.values.forEach(function (raw, i) {
        var v = (raw === null || raw === undefined || isNaN(raw)) ? null : Number(raw);
        if (v === null) { if (current.length) { runs.push(current); current = []; } }
        else { current.push([x(i), y(v)]); }
      });
      if (current.length) runs.push(current);
      var body = runs.map(function (run) {
        return '<polyline points="' + run.map(function (p) { return p[0] + ',' + p[1]; }).join(' ') +
          '" fill="none" stroke="' + s.color + '" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>';
      }).join('');
      var dots = runs.map(function (run) {
        return run.map(function (p, i) {
          if (run.length > 20 && i % 2) return '';
          return '<circle cx="' + p[0] + '" cy="' + p[1] + '" r="3" fill="var(--surface)" stroke="' + s.color + '" stroke-width="1.8"/>';
        }).join('');
      }).join('');
      return body + dots;
    }).join('');

    return '<svg class="chart" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid meet" role="img" aria-label="图表">' +
      grid + xAxis + lines + '</svg>';
  }

  function niceTicks(min, max) {
    if (min === max) { min = min - 1; max = max + 1; }
    var span = max - min;
    var steps = 4;
    var raw = span / steps;
    var mag = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10));
    var norm = raw / mag;
    var stepSize = (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10) * mag;
    var start = Math.floor(min / stepSize) * stepSize;
    var ticks = [];
    for (var v = start; v <= max + stepSize * 0.5 && ticks.length < 10; v += stepSize) {
      ticks.push(Math.round(v * 100) / 100);
    }
    return ticks.reverse();
  }

  function barChart(opts) {
    var rows = opts.rows || [];
    if (!rows.length) return '<div class="notice">' + esc(opts.empty || '该区间暂无数据') + '</div>';
    var max = 100;
    var bar = 'height:8px;border-radius:4px;background:var(--brand);';
    var body = rows.slice(0, 12).map(function (r) {
      var cpu = r.cpu === null || r.cpu === undefined ? null : Number(r.cpu);
      var mem = r.memory === null || r.memory === undefined ? null : Number(r.memory);
      return '<div style="display:flex;flex-direction:column;gap:6px;padding:8px 0;border-bottom:1px solid var(--border)">' +
        '<div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px">' +
        '<span style="font-size:13px;color:var(--text-1)">' + esc(r.name) + '</span>' +
        '<span class="kpi-trend mono">' + esc(r.ip || '') + '</span></div>' +
        '<div style="display:flex;align-items:center;gap:8px"><span class="kpi-trend" style="width:64px">CPU ' +
        (cpu === null ? '—' : cpu.toFixed(0) + '%') + '</span>' +
        '<span style="flex:1;background:var(--surface-sunken);border-radius:4px;height:8px;display:block">' +
        '<i style="display:block;width:' + (cpu === null ? 0 : Math.min(100, cpu)) + '%;' + bar + '"></i></span></div>' +
        '<div style="display:flex;align-items:center;gap:8px"><span class="kpi-trend" style="width:64px">内存 ' +
        (mem === null ? '—' : mem.toFixed(0) + '%') + '</span>' +
        '<span style="flex:1;background:var(--surface-sunken);border-radius:4px;height:8px;display:block">' +
        '<i style="display:block;width:' + (mem === null ? 0 : Math.min(100, mem)) + '%;' + bar + 'background:var(--success)"></i></span></div>' +
        '</div>';
    }).join('');
    return '<div>' + body + '<div class="legend" style="margin-top:10px">' +
      '<span class="li"><i class="sw" style="background:var(--brand)"></i>CPU 使用率</span>' +
      '<span class="li"><i class="sw" style="background:var(--success)"></i>内存使用率</span>' +
      '<span class="li">采集时间：' + esc(rows[0].time || '—') + '</span></div></div>';
  }

  function legendOf(series, extra) {
    return '<div class="legend">' + (series || []).map(function (s) {
      return '<span class="li"><i class="sw" style="background:' + s.color + '"></i>' + esc(s.name) + '</span>';
    }).join('') + (extra ? '<span class="li">' + esc(extra) + '</span>' : '') + '</div>';
  }

  /* ---------- 页面：01 巡检总览 ---------- */
  function pageOverview(data) {
    var trend = data.trend || { labels: [], series: [] };
    var health = data.health || {};
    var res = data.resources || { series: [], devices: [] };
    var recent = data.recent_inspections || [];
    var alertRows = (data.alerts || {}).recent || [];
    var severity = ((data.alerts || {}).by_severity) || {};
    var changeTotal = (data.alerts || {}).change_total || 0;
    var changeRows = (data.alerts || {}).change_recent || [];
    var validTabs = ['health', 'resources', 'inspections', 'alerts'];
    var tab = validTabs.indexOf(STATE.overviewTab) >= 0 ? STATE.overviewTab : 'health';
    STATE.overviewTab = tab;

    var head =
      topbar('搜索设备名称 / IP 地址 / 报告编号') +
      '<div class="page-head"><div class="page-title"><h1>网络设备巡检总览</h1>' +
      '<div class="page-sub"><span>统计区间：' + esc((data.period || {}).label || '') + '</span>' +
      '<span>已生成报告 ' + esc((data.kpis || [])[3] ? data.kpis[3].value : '0') + ' 份</span></div></div>' +
      '<div class="cta-row">' +
      '<a class="btn btn-ghost" href="#/wall">' + icon('monitor', 14) + '大屏轮播</a>' +
      '<a class="btn btn-primary" href="#/pending?tab=pending">' + icon('download', 14) + '设备采集</a></div></div>';

    var periodChips = '<div class="chip-row">' + [1, 7, 30, 90].map(function (d) {
      var on = Number(STATE.days) === d;
      return '<span class="chip' + (on ? ' brand' : '') + '" data-days="' + d + '" style="cursor:pointer">近 ' + d + ' 天</span>';
    }).join('') + '</div>';

    var healthChart = lineChart({
      labels: trend.labels, series: trend.series, yTicks: trend.yTicks,
      empty: '所选区间内还没有巡检记录，去「设备采集」执行一轮采集或改用别的区间'
    });
    var healthTone = health.avg_score >= 95 ? 'success' : 'warning';
    var healthCard = '<div class="card overview-module-card">' +
      cardHead('巡检健康度趋势', '数据来源：' + esc((data.period || {}).label || '') + ' 本平台采集记录（按天均值）', periodChips) +
      healthChart +
      '<div class="module-fact-strip">' +
      '<div class="module-fact-primary"><span>整体健康度</span><b>' +
      (health.avg_score === null || health.avg_score === undefined ? '—' : esc(health.avg_score)) + '</b>' +
      tag(health.avg_score >= 95 ? '优良' : health.avg_score === null || health.avg_score === undefined ? '待采集' : '需关注', healthTone) + '</div>' +
      '<div class="module-fact-grid">' + statList(health.summary || []) + '</div></div></div>';

    var resourceBody = STATE.resourceMode === 'devices'
      ? barChart({ rows: res.devices || [], empty: '还没有 SNMP / 遥测采集到的 CPU、内存数据' })
      : lineChart({
          labels: res.labels || [], series: res.series, unit: '%',
          empty: '还没有 SNMP / 遥测采集到的 CPU、内存数据'
        });
    var resLegend = STATE.resourceMode === 'devices' ? '' : legendOf(res.series || [], '按天均值');
    var resourceCard = '<div class="card overview-module-card">' +
      cardHead('设备 CPU / 内存使用率', '数据来源：本平台采集的 CPU / 内存 / 温度指标',
        '<div class="chip-row">' +
        '<span class="chip' + (STATE.resourceMode === 'trend' ? ' brand' : '') + '" data-res="trend" style="cursor:pointer">按天曲线</span>' +
        '<span class="chip' + (STATE.resourceMode === 'devices' ? ' brand' : '') + '" data-res="devices" style="cursor:pointer">按设备</span>' +
        '</div>') +
      resourceBody + '<div style="margin-top:10px">' + resLegend + '</div></div>';

    var inspectView = clientPage(recent, STATE, 'overviewInspectPage', 'overviewInspectSize', [10, 20, 50], 10);
    var inspectCard = '<div class="card tight overview-module-card">' +
      cardHead('最近巡检记录', '共 ' + esc((data.counts || {}).inspections || recent.length) + ' 条巡检记录',
        '<a class="link" href="#/devices">查看设备清单</a>') +
      '<div style="overflow-x:auto">' + (inspectView.rows.length ? table(
        [{ text: '巡检对象', width: 220 }, { text: '设备类型', width: 130 }, { text: '巡检时间', width: 180 }, { text: '责任人 / 资产编号' }, { text: '健康度' }, { text: '状态' }],
        inspectView.rows.map(function (r) {
          return [
            { text: r.target, cls: 'strong' }, { text: r.type }, { text: r.time, cls: 'mono' },
            { html: '<span>' + esc(r.owner || '—') + '</span><br/><span class="kpi-trend mono">' + esc(r.asset_no || '—') + '</span>' },
            { text: r.score, cls: 'strong mono' },
            { html: tag(r.status, r.tone || 'success') }
          ];
        })
      ) : emptyTable([{ text: '巡检对象' }, { text: '设备类型' }, { text: '巡检时间' }, { text: '责任人 / 资产编号' }, { text: '健康度' }, { text: '状态' }],
        '还没有巡检记录，采集到数据后这里会自动出现')) + '</div>' +
      pagerFooter('ovInspect', inspectView, '条') + '</div>';

    var alertCard = '<div class="card overview-module-card">' +
      cardHead('告警概览', '近 ' + esc((data.counts || {}).alerts || 0) + ' 条 · 聚合 ' + esc((data.alerts || {}).group_total || 0) +
        ' 组 · 未恢复 ' + esc((data.counts || {}).open_alerts || 0) + ' 条',
        '<a class="link" href="#/alerts">进入告警中心</a>') +
      '<div class="module-alert-facts">' +
      '<span class="chip warning">紧急 ' + esc(severity.critical || 0) + '</span>' +
      '<span class="chip warning">重要 ' + esc(severity.major || 0) + '</span>' +
      '<span class="chip">警告 ' + esc(severity.warning || 0) + '</span>' +
      '<span class="chip success">提示 ' + esc(severity.info || 0) + '</span>' +
      (changeTotal ? '<span class="chip brand">变化告警 ' + esc(changeTotal) + '</span>' : '') + '</div>' +
      (changeRows.length ? '<div class="module-subtitle">采集变化提醒（跟该设备上一轮采集对比）</div>' +
        '<div class="stat-list module-scroll-list">' + changeRows.slice(0, 8).map(function (c) {
          return '<div class="stat-item"><span class="n" style="white-space:normal">' + esc(c.title) + '</span>' +
            '<span class="v">' + esc(c.device) + ' · ' + esc(c.time) + '</span></div>';
        }).join('') + '</div>' : '') +
      '<div class="module-subtitle">最近未恢复告警</div>' +
      (alertRows.length ? '<div class="stat-list module-scroll-list">' + alertRows.slice(0, 10).map(function (a) {
        return '<div class="stat-item"><span class="n" style="white-space:normal">' + esc(a.title) + '</span>' +
          '<span class="v">' + esc(a.device) + ' · ' + esc(a.time) + '</span>' +
          '<span style="margin-left:auto">' + tag(a.status || '未处理', 'warning') + '</span></div>';
      }).join('') + '</div>' : notice('暂无告警记录', 'neutral')) + '</div>';

    var tabs = moduleTabs([
      { key: 'health', label: '健康趋势', icon: 'gauge', count: health.avg_score === null || health.avg_score === undefined ? '待采集' : health.avg_score },
      { key: 'resources', label: '资源使用', icon: 'cpu', count: (res.devices || []).length },
      { key: 'inspections', label: '巡检记录', icon: 'archive', count: recent.length },
      { key: 'alerts', label: '告警概览', icon: 'alert', count: (data.alerts || {}).group_total || 0 }
    ], tab, 'overview-tab', '<span>按标签页切换对应分析模块</span>');

    var body = tab === 'resources' ? resourceCard : tab === 'inspections' ? inspectCard : tab === 'alerts' ? alertCard : healthCard;
    return head + sourceNotice(data.source_info, data.source) + kpiCards(data.kpis || []) + tabs + body;
  }

  function overviewQuery() {
    return 'tab=' + encodeURIComponent(STATE.overviewTab || 'health') +
      '&inspect_page=' + (STATE.overviewInspectPage || 1) +
      '&inspect_size=' + (STATE.overviewInspectSize || 10);
  }

  function applyOverviewQuery(query) {
    if (['health', 'resources', 'inspections', 'alerts'].indexOf(query.tab) >= 0) STATE.overviewTab = query.tab;
    if (query.inspect_page) STATE.overviewInspectPage = Number(query.inspect_page) || 1;
    if ([10, 20, 50].indexOf(Number(query.inspect_size)) >= 0) STATE.overviewInspectSize = Number(query.inspect_size);
  }

  function bindOverview() {
    document.querySelectorAll('[data-days]').forEach(function (chip) {
      chip.addEventListener('click', function () {
        STATE.days = Number(chip.getAttribute('data-days'));
        refreshPageHash('overview', overviewQuery());
      });
    });
    document.querySelectorAll('[data-res]').forEach(function (chip) {
      chip.addEventListener('click', function () {
        STATE.resourceMode = chip.getAttribute('data-res');
        refreshPageHash('overview', overviewQuery());
      });
    });
    bindModuleTabs('overview-tab', function (tab) {
      STATE.overviewTab = tab;
      refreshPageHash('overview', overviewQuery());
    });
    bindClientPager('ovInspect', STATE, 'overviewInspectPage', 'overviewInspectSize', function () {
      refreshPageHash('overview', overviewQuery());
    });
  }

  /* ---------- 页面：02 设备清单 ---------- */
  function pageDevices(data) {
    var s = data.summary || {};
    var facets = data.facets || {};
    var d = STATE.devices;

    var typeOptions = [{ value: 'all', label: '全部类型' },
      { value: 'server', label: '服务器（全部）' }, { value: 'switch', label: '网络设备（全部）' },
      { value: 'security', label: '安全设备（全部）' }]
      .concat((facets.types || []).map(function (t) {
        return { value: t.value, label: t.label + '（' + t.count + '）' };
      }));
    var groupOptions = [{ value: 'all', label: '全部分组' }].concat(
      (facets.groups || []).map(function (g) { return { value: g.value, label: g.label + '（' + g.count + '）' }; }));
    var statusOptions = [{ value: 'all', label: '全部健康状态' }, { value: 'normal', label: '正常' },
      { value: 'warning', label: '需关注' }, { value: 'danger', label: '异常 / 离线' },
      { value: 'unknown', label: '未巡检' }];
    var onlineOptions = [{ value: 'all', label: '全部连接状态' },
      { value: '1', label: '在线' }, { value: '0', label: '离线 / 待配置' }];

    function filterInput(key, value, placeholder) {
      return '<input class="grid-filter-input" data-dvf="' + key + '" value="' + esc(value || '') +
        '" placeholder="' + esc(placeholder || '筛选') + '" autocomplete="off"/>';
    }
    function filterSelect(key, options, value) {
      return '<select class="grid-filter-select" data-dvf="' + key + '">' + options.map(function (o) {
        return '<option value="' + esc(o.value) + '"' + (String(o.value) === String(value) ? ' selected' : '') + '>' +
          esc(o.label) + '</option>';
      }).join('') + '</select>';
    }

    var head =
      topbar('搜索设备名称 / IP / 责任人 / 资产编号') +
      '<div class="page-head device-page-head"><div class="page-title"><h1>设备台账</h1>' +
      '<div class="page-sub"><span id="dvSummaryLine">共 ' + esc(s.total || 0) + ' 台设备 · 服务器 ' + esc(s.servers || 0) +
      ' 台 · 网络设备 ' + esc(s.switches || 0) + ' 台 · 安全设备 ' + esc(s.security || 0) +
      ' 台 · 在线 ' + esc(s.online || 0) + ' 台 · 需关注 ' + esc(s.abnormal || 0) + ' 台</span>' +
      '<span id="dvMatchLine">匹配 ' + esc(data.total || 0) + ' 条 · 数据源 ' + esc(data.source_label || '') + '</span></div></div>' +
      '<div class="cta-row">' +
      '<button class="btn btn-ghost" id="dvResetFilters">重置筛选</button>' +
      '<button class="btn btn-ghost" id="dvExport">导出台账</button>' +
      '</div></div>';

    var cols = [
      { html: '<input type="checkbox" id="dvSelectAll" title="选中当前页全部设备"/>', width: 42 },
      { text: '序号', width: 58 },
      { html: '设备角色', width: 165, filterHtml: filterInput('role', d.role, '筛选角色') },
      { html: '设备名称（主机名）', width: 190, filterHtml: filterInput('name', d.name, '筛选名称') },
      { html: '设备类型', width: 125, filterHtml: filterSelect('type', typeOptions, d.type) },
      { html: '品牌型号及配置', width: 210, filterHtml: filterInput('model', d.model, '筛选型号') },
      { html: '系统版本', width: 145, filterHtml: filterInput('version', d.version, '筛选版本') },
      { html: 'IP 地址', width: 135, filterHtml: filterInput('ip', d.ip, '筛选 IP') },
      { html: '连接状态', width: 118, filterHtml: filterSelect('online', onlineOptions, d.online) },
      { html: '健康状态', width: 125, filterHtml: filterSelect('status', statusOptions, d.status) },
      { text: '操作', width: 150 }
    ];

    var rows = (data.rows || []).map(function (dev, i) {
      var no = String((data.page - 1) * data.page_size + i + 1);
      var noIp = /^noip-/i.test(String(dev.ip || ''));
      var selected = !!STATE.deviceSelected[dev.ip];
      var cells = [
        { html: '<input type="checkbox" class="device-select-check" data-select-device="' + esc(dev.ip) +
            '" data-select-name="' + esc(dev.name || dev.ip) + '"' + (selected ? ' checked' : '') + '/>', cls: 'select-cell' },
        { text: no, cls: 'dim mono' },
        { text: dev.role || '—', cls: 'device-role-cell' },
        { html: noIp ? esc(dev.name || '—') : '<a class="link" title="查看该设备健康检查" href="#/' +
            (['server','security'].indexOf(dev.group_kind) >= 0 ? dev.group_kind : 'switch') +
            '?device=' + encodeURIComponent(dev.ip) + '">' + esc(dev.name || dev.ip) + '</a>', cls: 'strong' },
        { text: dev.type_label },
        { text: dev.model || '—' },
        { text: dev.version || '—' },
        { text: noIp ? '待配置管理IP' : dev.ip, cls: 'mono' },
        { html: '<span class="status-text ' + (noIp ? 'warning' : (dev.online ? 'success' : 'danger')) + '" title="' +
            esc(noIp ? '台账设备：尚未配置管理 IP 和采集凭据' : (dev.last_error || (dev.last_checked_at ? '最近探测 ' + dev.last_checked_at : '尚未采集/探测'))) +
            '">' + (noIp ? '待配置IP' : (dev.online ? '在线' : '离线')) + '</span>' },
        { html: '<span class="status-text ' + toneClass(dev.health_tone) + '">' + esc(dev.health_label) + '</span>' +
            (dev.health_score === null || dev.health_score === undefined ? '' :
              ' <span class="kpi-trend mono">' + dev.health_score + '</span>') },
        { html: '<a class="link" data-ledger="' + esc(dev.ip) + '" style="cursor:pointer">台账</a>' +
            (noIp || dev.group_kind === 'server' ? '' :
              ' · <a class="link" data-remote="' + esc(dev.ip) + '" style="cursor:pointer">远程</a>') +
            (can('ledger_write') ? ' · <a class="danger-link" data-deldev="' + esc(dev.ip) + '" data-delname="' + esc(dev.name || dev.ip) + '" style="cursor:pointer">删除</a>' : '') }
      ];
      cells.rowAttr = 'data-device-row="' + esc(dev.ip) + '" class="' + (selected ? 'device-row-selected' : '') + '"';
      return cells;
    });

    var bulk = '<div class="device-bulk-bar" id="deviceBulkBar">' +
      '<div class="device-bulk-count"><b id="dvSelectedCount">0</b><span>台设备已选中</span></div>' +
      '<span class="device-bulk-hint">勾选左侧方框，可对当前页设备执行批量操作</span>' +
      '<div class="btn-group">' +
      (can('ledger_write') ? '<button class="btn btn-ghost sm danger-link" id="dvBulkDelete" style="color:var(--danger)" disabled>批量删除</button>' : '') +
      '<button class="btn btn-ghost sm" id="dvClearSelection" disabled>取消选择</button>' +
      '</div></div>';

    var list = '<div class="card tight device-list-card">' +
      cardHead('设备清单', '<span id="dvListSub">共 ' + esc(data.total || 0) + ' 条记录 · 第 ' + esc(data.page) + '/' + esc(data.pages) + ' 页</span>',
        '<span class="device-list-tools"><span class="kpi-trend">数据源：' + esc(data.source_label || '') + '</span></span>') +
      bulk +
      '<div class="device-grid-wrap">' +
      (rows.length ? table(cols, rows) : emptyTable(cols, '没有符合条件的设备：调整筛选条件，或先到「待采集设备」新增/导入并完成在线采集')) +
      '</div>' +
      pagerFooter('dv', { total: data.total, page: data.page, pages: data.pages, size: data.page_size }, '条记录') +
      '</div>';

    return head + sourceNotice(data.source_info, data.source) + list;
  }

  function devicesQuery() {
    var d = STATE.devices;
    var parts = [];
    ['keyword', 'type', 'vendor', 'group', 'region', 'status', 'online',
     'name', 'role', 'model', 'version', 'ip', 'owner', 'location', 'asset_no',
     'usage', 'warranty_until', 'note', 'sort', 'order', 'page', 'page_size'].forEach(function (key) {
      var value = d[key];
      if (value === undefined || value === null || value === '' || value === 'all') return;
      if ((key === 'sort' && value === 'ip') || (key === 'order' && value === 'asc')) return;
      if (key === 'page' && Number(value) <= 1) return;
      if (key === 'page_size' && Number(value) === 10) return;
      parts.push(key + '=' + encodeURIComponent(value));
    });
    return parts.join('&');
  }

  function applyDevicesQuery(query) {
    var d = STATE.devices;
    d.keyword = query.keyword || '';
    d.type = query.type || 'all';
    d.vendor = query.vendor || 'all';
    d.group = query.group || 'all';
    d.region = query.region || 'all';
    d.status = query.status || 'all';
    d.online = query.online || 'all';
    d.name = query.name || '';
    d.role = query.role || '';
    d.model = query.model || '';
    d.version = query.version || '';
    d.ip = query.ip || '';
    d.owner = query.owner || '';
    d.location = query.location || '';
    d.asset_no = query.asset_no || '';
    d.usage = query.usage || '';
    d.warranty_until = query.warranty_until || '';
    d.note = query.note || '';
    d.sort = query.sort || 'ip';
    d.order = query.order || 'asc';
    d.page = Number(query.page || 1) || 1;
    d.page_size = Number(query.page_size || 10) || 10;
  }

  /** 健康/状态色 → 现有 CSS 的类名（原型里的 status-text 只有 4 种） */
  /** 数据源中文名（页面角标与说明文字用） */
  function sourceLabelOf(source) {
    return '本平台自带采集';
  }

  function toneClass(tone) {
    return tone === 'success' ? 'success' : tone === 'danger' ? 'danger'
      : tone === 'warning' ? 'warning' : 'muted';
  }

  function openDeleteDeviceModal(ip, name, onDeleted) {
    var inner = '<div class="modal" style="width:520px">' +
      '<div class="card-head"><div class="t"><div class="title" style="font-size:18px">删除设备</div>' +
      '<div class="sub">' + esc(name || '') + ' · ' + esc(ip) + '</div></div>' +
      '<button class="icon-btn" style="width:32px;height:32px" data-overlay-cancel>' + icon('close', 16) + '</button></div>' +
      notice('删除后该设备会从设备清单中移除。建议勾选“同时清理关联数据”，否则可能留下无法关联的巡检、告警和备份记录。', 'danger') +
      '<label class="radio" style="font-size:13px;color:var(--text-2)">' +
      '<input id="delPurge" type="checkbox" checked style="width:14px;height:14px"/> 同时清理巡检、告警、备份、凭据和采集日志</label>' +
      '<div class="footer-bar"><span class="kpi-trend">此操作不可撤销，建议先下载平台备份</span>' +
      '<div class="btn-group"><button class="btn btn-ghost" data-overlay-cancel>取消</button>' +
      '<button class="btn btn-primary" id="delConfirm" style="background:var(--danger);border-color:var(--danger)">确认删除</button></div></div></div>';
    showOverlay(inner, false);
    var btn = document.getElementById('delConfirm');
    if (btn) btn.addEventListener('click', function () {
      var purge = !!(document.getElementById('delPurge') || {}).checked;
      btn.textContent = '删除中…';
      window.NetInspect.deleteDevice(ip, purge).then(function () {
        closeOverlay();
        showToast('已删除 ' + ip);
        if (onDeleted) onDeleted([ip]);
      }).catch(function (err) {
        btn.textContent = '确认删除';
        showToast('删除失败：' + err.message);
      });
    });
  }

  function openDemoCleanupModal(onDeleted) {
    window.NetInspect.demoDeviceCandidates().then(function (res) {
      var candidates = res.devices || [];
      if (!candidates.length) { showToast('没有检测到测试设备'); return; }
      var rows = candidates.map(function (d) {
        var c = d.counts || {};
        return '<label class="stat-item" style="height:auto;padding:10px 0;align-items:flex-start;gap:10px">' +
          '<input type="checkbox" data-clean-ip="' + esc(d.ip) + '" checked style="width:14px;height:14px;margin-top:2px"/>' +
          '<span style="min-width:0;display:flex;flex-direction:column;gap:3px">' +
          '<b>' + esc(d.name || d.ip) + '</b>' +
          '<span class="mono kpi-trend">' + esc(d.ip) + ' · 巡检 ' + (c.inspections || 0) +
          ' · 告警 ' + (c.alerts || 0) + ' · 备份 ' + (c.backups || 0) + '</span></span></label>';
      }).join('');
      var inner = '<div class="modal" style="width:680px">' +
        '<div class="card-head"><div class="t"><div class="title" style="font-size:18px">清理测试数据</div>' +
        '<div class="sub">只列出 10.20.* 或台账备注含“演示”的设备，请确认后再删除</div></div>' +
        '<button class="icon-btn" style="width:32px;height:32px" data-overlay-cancel>' + icon('close', 16) + '</button></div>' +
        '<div class="summary-bar" style="background:var(--danger-soft-bg)">' +
        '<div class="info"><span class="n">共 ' + candidates.length + ' 台测试设备</span>' +
        '<span class="m">可勾选需要删除的设备，默认全选；正式设备不会被此窗口删除</span></div></div>' +
        '<div style="max-height:340px;overflow:auto">' + rows + '</div>' +
        '<label class="radio" style="font-size:13px;color:var(--text-2)">' +
        '<input id="cleanPurge" type="checkbox" checked style="width:14px;height:14px"/> 同时清理关联巡检、告警、备份、凭据和采集日志</label>' +
        '<div class="footer-bar"><span class="kpi-trend">删除不可撤销，建议先下载平台备份</span>' +
        '<div class="btn-group"><button class="btn btn-ghost" data-overlay-cancel>取消</button>' +
        '<button class="btn btn-primary" id="cleanConfirm" style="background:var(--danger);border-color:var(--danger)">清理勾选设备</button></div></div></div>';
      showOverlay(inner, false);
      var btn = document.getElementById('cleanConfirm');
      if (btn) btn.addEventListener('click', function () {
        var ips = [];
        Array.prototype.forEach.call(document.querySelectorAll('[data-clean-ip]:checked'), function (x) {
          ips.push(x.getAttribute('data-clean-ip'));
        });
        if (!ips.length) { showToast('请至少勾选一台设备'); return; }
        var purge = !!(document.getElementById('cleanPurge') || {}).checked;
        btn.textContent = '清理中…';
        window.NetInspect.purgeDemoDevices(ips, purge).then(function (out) {
          closeOverlay();
          showToast('已清理 ' + (out.count || 0) + ' 台测试设备');
          if (onDeleted) onDeleted(out.removed || []);
        }).catch(function (err) {
          btn.textContent = '清理勾选设备';
          showToast('清理失败：' + err.message);
        });
      });
    }).catch(function (err) { showToast('读取测试数据失败：' + err.message); });
  }

  

  function renumberDeviceRows() {
    var tableBody = document.querySelector('#main table.grid tbody');
    if (!tableBody) return;
    var offset = (Number(STATE.devices.page || 1) - 1) * Number(STATE.devices.page_size || 10);
    Array.prototype.forEach.call(tableBody.querySelectorAll('tr[data-device-row]'), function (row, i) {
      var first = row.querySelector('td');
      if (first) first.textContent = String(offset + i + 1);
    });
  }

  function updateDeviceListChrome(data) {
    var s = data.summary || {};
    var summary = document.getElementById('dvSummaryLine');
    if (summary) {
      summary.textContent = '共 ' + (s.total || 0) + ' 台设备 · 服务器 ' + (s.servers || 0) +
        ' 台 · 网络设备 ' + (s.switches || 0) + ' 台 · 安全设备 ' + (s.security || 0) +
        ' 台 · 在线 ' + (s.online || 0) + ' 台 · 需关注 ' + (s.abnormal || 0) + ' 台';
    }
    var matched = document.getElementById('dvMatchLine');
    if (matched) matched.textContent = '匹配 ' + (data.total || 0) + ' 条 · 数据源 ' + (data.source_label || '');
    var listSub = document.getElementById('dvListSub');
    if (listSub) listSub.textContent = '共 ' + (data.total || 0) + ' 条记录 · 第 ' + data.page + '/' + data.pages + ' 页';
    var footer = document.getElementById('dvFooterCount');
    if (footer) footer.textContent = '共 ' + (data.total || 0) + ' 条记录 · 第 ' + (data.page || 1) + ' / ' + (data.pages || 1) + ' 页';
    var pageNo = document.getElementById('dvPageNo');
    if (pageNo) pageNo.innerHTML = String(data.page || 1) + ' <em>/ ' + (data.pages || 1) + '</em>';
  }

  function applyDeviceDeletionToView(data, removedIps) {
    var wanted = {};
    var now = Date.now();
    (removedIps || []).forEach(function (ip) {
      wanted[ip] = true;
      STATE.deviceDeletedIps[ip] = now;
      delete STATE.deviceSelected[ip];
    });
    var visibleRemoved = [];
    Array.prototype.forEach.call(document.querySelectorAll('[data-deldev]'), function (link) {
      var ip = link.getAttribute('data-deldev');
      if (!wanted[ip]) return;
      var row = link.closest('tr');
      if (!row) return;
      var device = (data.rows || []).filter(function (d) { return d.ip === ip; })[0];
      if (device) visibleRemoved.push(device);
      row.parentNode.removeChild(row);
    });
    data.rows = (data.rows || []).filter(function (d) { return !wanted[d.ip]; });
    data.summary = data.summary || {};
    data.summary.total = Math.max(0, Number(data.summary.total || 0) - Object.keys(wanted).length);
    visibleRemoved.forEach(function (d) {
      if (d.group_kind === 'server') data.summary.servers = Math.max(0, Number(data.summary.servers || 0) - 1);
      else if (d.group_kind === 'security') data.summary.security = Math.max(0, Number(data.summary.security || 0) - 1);
      else data.summary.switches = Math.max(0, Number(data.summary.switches || 0) - 1);
      if (d.online) data.summary.online = Math.max(0, Number(data.summary.online || 0) - 1);
      if (d.health_status && d.health_status !== 'normal') {
        data.summary.abnormal = Math.max(0, Number(data.summary.abnormal || 0) - 1);
      }
    });
    data.total = Math.max(0, Number(data.total || 0) - visibleRemoved.length);
    data.pages = Math.max(1, Math.ceil(Number(data.total || 0) / Math.max(1, Number(data.page_size || 10))));
    var tableBody = document.querySelector('#main table.grid tbody');
    if (tableBody && !tableBody.querySelector('tr[data-device-row]')) {
      tableBody.innerHTML = '<tr><td colspan="13" class="dim">当前页设备已全部删除，可切换上一页或重新查询</td></tr>';
    }
    renumberDeviceRows();
    updateDeviceListChrome(data);
    updateDeviceSelectionChrome();
  }


  function updateDeviceSelectionChrome() {
    var checks = Array.prototype.slice.call(document.querySelectorAll('.device-select-check'));
    var checked = checks.filter(function (cb) { return cb.checked; });
    var count = Object.keys(STATE.deviceSelected || {}).length;
    var countEl = document.getElementById('dvSelectedCount');
    if (countEl) countEl.textContent = String(count);
    var bar = document.getElementById('deviceBulkBar');
    if (bar) bar.classList.toggle('active', count > 0);
    var clearBtn = document.getElementById('dvClearSelection');
    if (clearBtn) clearBtn.disabled = count === 0;
    var deleteBtn = document.getElementById('dvBulkDelete');
    if (deleteBtn) deleteBtn.disabled = count === 0;
    var all = document.getElementById('dvSelectAll');
    if (all) {
      all.disabled = checks.length === 0;
      all.checked = checks.length > 0 && checked.length === checks.length;
      all.indeterminate = checked.length > 0 && checked.length < checks.length;
    }
  }

  function clearDeviceSelection() {
    STATE.deviceSelected = {};
    Array.prototype.forEach.call(document.querySelectorAll('.device-select-check'), function (cb) {
      cb.checked = false;
      var row = cb.closest('tr');
      if (row) row.classList.remove('device-row-selected');
    });
    updateDeviceSelectionChrome();
  }

  function selectedDeviceRows(data) {
    return (data.rows || []).filter(function (dev) { return !!STATE.deviceSelected[dev.ip]; });
  }

  function openBulkDeleteDevicesModal(devices, onDeleted) {
    var list = devices || [];
    if (!list.length) { showToast('请先选择设备'); return; }
    var preview = list.slice(0, 10).map(function (d) { return '<span>' + esc(d.name || d.ip) + '</span>'; }).join('');
    if (list.length > 10) preview += '<span>…其余 ' + (list.length - 10) + ' 台</span>';
    var inner = '<div class="modal" style="width:620px">' +
      '<div class="card-head"><div class="t"><div class="title" style="font-size:18px">批量删除设备</div>' +
      '<div class="sub">已选中 ' + list.length + ' 台设备，请确认操作范围</div></div>' +
      '<button class="icon-btn" style="width:32px;height:32px" data-overlay-cancel>' + icon('close', 16) + '</button></div>' +
      notice('删除后设备会从清单、大屏和后续采集中移除。建议同时清理关联巡检、告警、备份和凭据。', 'danger') +
      '<div class="bulk-delete-preview">' + preview + '</div>' +
      '<label class="radio" style="font-size:13px;color:var(--text-2)">' +
      '<input id="bulkDelPurge" type="checkbox" checked style="width:14px;height:14px"/> 同时清理巡检、告警、备份、凭据和采集日志</label>' +
      '<div class="footer-bar"><span class="kpi-trend">批量删除不可撤销</span><div class="btn-group">' +
      '<button class="btn btn-ghost" data-overlay-cancel>取消</button>' +
      '<button class="btn btn-primary" id="bulkDelConfirm" style="background:var(--danger);border-color:var(--danger)">确认删除 ' + list.length + ' 台</button>' +
      '</div></div></div>';
    showOverlay(inner, false);
    var btn = document.getElementById('bulkDelConfirm');
    if (!btn) return;
    btn.addEventListener('click', function () {
      var purge = !!(document.getElementById('bulkDelPurge') || {}).checked;
      var ips = list.map(function (d) { return d.ip; });
      var failures = [];
      btn.disabled = true;
      btn.textContent = '删除中…';
      var chain = Promise.resolve();
      ips.forEach(function (ip) {
        chain = chain.then(function () {
          return window.NetInspect.deleteDevice(ip, purge).catch(function (err) {
            failures.push(ip + '：' + err.message);
          });
        });
      });
      chain.then(function () {
        closeOverlay();
        var deleted = ips.filter(function (ip) { return failures.every(function (f) { return f.indexOf(ip + '：') !== 0; }); });
        deleted.forEach(function (ip) { delete STATE.deviceSelected[ip]; });
        showToast(failures.length ? ('已删除 ' + deleted.length + ' 台，失败 ' + failures.length + ' 台') : ('已批量删除 ' + deleted.length + ' 台'));
        if (onDeleted) onDeleted(deleted);
        updateDeviceSelectionChrome();
      });
    });
  }

  function bindDevices(data) {
    function readColumnFilters() {
      Array.prototype.forEach.call(document.querySelectorAll('[data-dvf]'), function (node) {
        var key = node.getAttribute('data-dvf');
        if (!key) return;
        STATE.devices[key] = node.value === '' && node.tagName === 'SELECT' ? 'all' : node.value;
      });
    }
    function submit(resetPage, preserveSelection) {
      readColumnFilters();
      if (resetPage) STATE.devices.page = 1;
      if (!preserveSelection) STATE.deviceSelected = {};
      var query = devicesQuery();
      var hash = '#/devices' + (query ? '?' + query : '');
      if (location.hash === hash) route(); else location.hash = hash;
    }

    Array.prototype.forEach.call(document.querySelectorAll('[data-dvf]'), function (node) {
      if (node.tagName === 'SELECT') {
        node.addEventListener('change', function () { submit(true, false); });
      } else {
        node.addEventListener('keydown', function (e) {
          if (e.key === 'Enter') { e.preventDefault(); submit(true, false); }
          if (e.key === 'Escape') { node.value = ''; submit(true, false); }
        });
        node.addEventListener('change', function () { submit(true, false); });
      }
    });

    var resetFilters = document.getElementById('dvResetFilters');
    if (resetFilters) resetFilters.addEventListener('click', function () {
      STATE.devices = { page: 1, page_size: 10, keyword: '', type: 'all', status: 'all',
        vendor: 'all', group: 'all', region: 'all', online: 'all',
        name: '', role: '', model: '', version: '', ip: '', owner: '', location: '',
        asset_no: '', usage: '', warranty_until: '', note: '', sort: 'ip', order: 'asc' };
      STATE.deviceSelected = {};
      var hash = '#/devices';
      if (location.hash === hash) route(); else location.hash = hash;
    });

    var pageSize = document.getElementById('dvSize');
    if (pageSize) pageSize.addEventListener('change', function () {
      readColumnFilters();
      STATE.devices.page_size = Number(pageSize.value) || 10;
      submit(true, false);
    });

    var prev = document.getElementById('dvPrev');
    if (prev) prev.addEventListener('click', function () {
      if (STATE.devices.page > 1) { STATE.devices.page -= 1; submit(false, false); }
    });
    var next = document.getElementById('dvNext');
    if (next) next.addEventListener('click', function () {
      STATE.devices.page += 1; submit(false, false);
    });

    var selectAll = document.getElementById('dvSelectAll');
    if (selectAll) selectAll.addEventListener('change', function () {
      Array.prototype.forEach.call(document.querySelectorAll('.device-select-check'), function (cb) {
        cb.checked = selectAll.checked;
        var ip = cb.getAttribute('data-select-device');
        if (selectAll.checked) STATE.deviceSelected[ip] = true; else delete STATE.deviceSelected[ip];
        var row = cb.closest('tr');
        if (row) row.classList.toggle('device-row-selected', cb.checked);
      });
      updateDeviceSelectionChrome();
    });
    Array.prototype.forEach.call(document.querySelectorAll('.device-select-check'), function (cb) {
      cb.addEventListener('change', function () {
        var ip = cb.getAttribute('data-select-device');
        if (cb.checked) STATE.deviceSelected[ip] = true; else delete STATE.deviceSelected[ip];
        var row = cb.closest('tr');
        if (row) row.classList.toggle('device-row-selected', cb.checked);
        updateDeviceSelectionChrome();
      });
    });

    var clearSelection = document.getElementById('dvClearSelection');
    if (clearSelection) clearSelection.addEventListener('click', clearDeviceSelection);

    var bulkDelete = document.getElementById('dvBulkDelete');
    if (bulkDelete) bulkDelete.addEventListener('click', function () {
      openBulkDeleteDevicesModal(selectedDeviceRows(data), function (ips) {
        applyDeviceDeletionToView(data, ips);
      });
    });

    var ex = document.getElementById('dvExport');
    if (ex) ex.addEventListener('click', function () {
      download(window.NetInspect.exportUrl({ kind: 'ledger', format: 'xlsx' }));
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-ledger]'), function (link) {
      link.addEventListener('click', function () { openLedger(link.getAttribute('data-ledger')); });
    });
    var cleanupDemo = document.getElementById('dvCleanupDemo');
    if (cleanupDemo) cleanupDemo.addEventListener('click', function () {
      openDemoCleanupModal(function (ips) {
        ips.forEach(function (ip) { delete STATE.deviceSelected[ip]; });
        applyDeviceDeletionToView(data, ips);
      });
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-deldev]'), function (link) {
      link.addEventListener('click', function () {
        openDeleteDeviceModal(link.getAttribute('data-deldev'), link.getAttribute('data-delname'), function (ips) {
          ips.forEach(function (ip) { delete STATE.deviceSelected[ip]; });
          applyDeviceDeletionToView(data, ips);
        });
      });
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-remote]'), function (link) {
      link.addEventListener('click', function () {
        STATE.remote.ip = link.getAttribute('data-remote');
        location.hash = '#/console?device=' + encodeURIComponent(STATE.remote.ip);
      });
    });
    updateDeviceSelectionChrome();
  }

  /* ---------- 页面：待采集设备（新增/导入 → 采集 → 转正式台账） ---------- */
  function pendingQuery() {
    var p = STATE.pending;
    var cu = STATE.collectUi || {};
    var f = STATE.collectFilter || {};
    var parts = [];
    if (p.tab && p.tab !== 'pending') parts.push('tab=' + encodeURIComponent(p.tab));
    if (p.keyword) parts.push('keyword=' + encodeURIComponent(p.keyword));
    if (Number(p.page) > 1) parts.push('page=' + p.page);
    if (Number(p.page_size) !== 10) parts.push('page_size=' + p.page_size);
    ['device_page','device_size','runs_page','runs_size','logs_page','logs_size'].forEach(function (key) {
      if (cu[key] !== undefined && cu[key] !== null && cu[key] !== '') parts.push(key + '=' + encodeURIComponent(cu[key]));
    });
    if (f.ip) parts.push('ip=' + encodeURIComponent(f.ip));
    if (f.only_failed) parts.push('only_failed=1');
    if (f.run_id) parts.push('run_id=' + encodeURIComponent(f.run_id));
    return parts.join('&');
  }

  function applyPendingQuery(query) {
    var p = STATE.pending;
    var cu = STATE.collectUi || (STATE.collectUi = {});
    p.keyword = query.keyword || '';
    p.page = Number(query.page || 1) || 1;
    p.page_size = Number(query.page_size || 10) || 10;
    p.sort = 'ip';
    p.order = 'asc';
    if (query.tab === 'execute') query.tab = 'pending';
    p.tab = ['pending','runs','logs','settings'].indexOf(query.tab) >= 0 ? query.tab : 'pending';
    cu.tab = ['runs','logs','settings'].indexOf(p.tab) >= 0 ? p.tab : 'devices';
    ['device_page','runs_page','logs_page'].forEach(function (key) {
      if (query[key] !== undefined) cu[key] = Number(query[key]) || 1;
    });
    ['device_size','runs_size','logs_size'].forEach(function (key) {
      if (query[key] !== undefined && [10,20,50].indexOf(Number(query[key])) >= 0) cu[key] = Number(query[key]);
    });
    STATE.collectFilter.ip = query.ip || '';
    STATE.collectFilter.only_failed = query.only_failed === '1';
    STATE.collectFilter.run_id = Number(query.run_id) || 0;
  }

  function pagePending(data) {
    var p = STATE.pending;
    var summary = data.summary || {};
    var rows = data.rows || [];
    var coll = data.collect || {};
    var cstats = (coll.stats || {})['7d'] || {};
    STATE.pendingCredentialsUnavailable = !!data.credentials_error;
    var pendingTab = ['pending','runs','logs','settings'].indexOf(p.tab) >= 0 ? p.tab : 'pending';
    p.tab = pendingTab;
    STATE.collect = coll;
    STATE.collectDevices = coll.devices || [];
    var candidates = {};
    (data.credentials || []).forEach(function (c) { candidates[c.ip] = c; });
    rows.forEach(function (d) {
      var cred = candidates[d.ip];
      d.credential = cred ? Object.assign({ configured: true }, cred) : { configured: false };
    });
    STATE.remoteDevices = rows.map(function (d) { d.category = d.group_kind; return d; });
    STATE.pendingDeviceCache = STATE.pendingDeviceCache || {};
    rows.forEach(function (d) { STATE.pendingDeviceCache[d.ip] = d; });

    var pendingActions = '';
    if (pendingTab === 'pending') {
      pendingActions = (can('ledger_write') ? '<button class="btn btn-ghost" id="pdTemplate">下载导入模板</button>' : '') +
        (can('ledger_write') ? '<button class="btn btn-ghost" id="pdImport">导入设备</button>' : '') +
        (can('ledger_write') ? '<button class="btn btn-primary" id="pdAdd">新增设备</button>' : '');
    } else if (pendingTab === 'runs' || pendingTab === 'logs') {
      pendingActions = can('sync') ? '<button class="btn btn-ghost" id="pdClearHistory">清理 30 天前历史</button>' : '';
    }
    var head = topbar('搜索待采集设备 / IP / 采集日志') +
      '<div class="page-head"><div class="page-title"><h1>设备采集中心</h1>' +
      '<div class="page-sub"><span>配置凭据后，勾选设备采集</span>' +
      '</div></div>' +
      '<div class="cta-row pending-cta">' + pendingActions +
      '<button class="icon-btn" id="pdRefresh" title="刷新" aria-label="刷新" style="width:36px;flex-basis:36px;margin-left:auto">' + icon('refresh', 16) + '</button></div></div>';

    var kpis = [
      { label: '待采集设备', value: String(summary.total || data.total || 0), unit: '台', note: '尚未完成有效在线采集', tone: 'warning' },
      { label: '凭据就绪', value: String(coll.credential_ready || 0), unit: '台', note: '未配置 ' + String(Math.max(0, (coll.devices_total || 0) - (coll.credential_ready || 0))) + ' 台', tone: (coll.credential_ready || 0) ? 'success' : 'warning' },
      { label: '近 7 天任务', value: String(cstats.runs || 0), unit: '次', note: '成功 ' + String(cstats.ok || 0) + ' / 失败 ' + String(cstats.failed || 0), tone: 'default' },
      { label: '采集成功率', value: (cstats.success_rate === null || cstats.success_rate === undefined) ? '—' : cstats.success_rate + '%',
        unit: '', note: '覆盖 ' + String(cstats.devices || 0) + ' 台设备', tone: (cstats.success_rate || 0) >= 95 ? 'success' : 'warning' }
    ];

    var cols = [
      { html: '<input type="checkbox" id="pdSelectAll" title="选中当前页全部设备"/>', width: 42 },
      { text: '序列号', width: 165 }, { text: '设备角色', width: 140 }, { text: 'IP 地址', width: 155 }, { text: '设备地点', width: 190 },
      { text: '凭据', width: 150 }, { text: '状态', width: 160 }, { text: '操作', width: 180 }
    ];
    var tableRows = rows.map(function (d, i) {
      var noIp = /^noip-/i.test(String(d.ip || ''));
      var cred = d.credential || { configured: false };
      var checked = !!STATE.pendingSelected[d.ip];
      var checkedAttr = checked ? ' checked' : '';
      var selectedClass = checked ? 'pending-row-selected' : '';
      var status = noIp ? '待配置IP' : (d.last_checked_at ? '待重试' : '待采集');
      var statusTone = noIp ? 'warning' : (d.last_checked_at ? 'danger' : 'warning');
      var cells = [
        { html: '<input type="checkbox" data-pending-select="' + esc(d.ip) + '"' + checkedAttr + '/>' },
        { text: d.serial || '—', cls: 'mono' },
        { text: d.role || '—' },
        { text: noIp ? '待配置管理IP' : d.ip, cls: 'mono strong' },
        { text: (d.ledger || {}).location || d.location || '—' },
        { html: cred.configured ? tag('已配置', 'success') : tag('未配置', 'warning') },
        { html: tag(status, statusTone) + (d.last_checked_at ? ' <span class="kpi-trend mono">' + esc(d.last_checked_at) + '</span>' : '') },
        { html: (!noIp && can('sync') ? '<button type="button" class="btn btn-ghost xs pending-single-collect" data-pending-collect="' + esc(d.ip) + '"' + (STATE.pendingCollectBusy || data.credentials_error ? ' disabled' : '') + '>采集</button> ' : '') + (!noIp && can('remote') ? '<a class="link" data-pending-cred="' + esc(d.ip) + '" style="cursor:pointer">' + (cred.configured ? '修改凭据' : '配置凭据') + '</a>' : '') +
            (can('ledger_write') ? ' · <a class="danger-link" data-pending-delete="' + esc(d.ip) + '" data-pending-name="' + esc(d.name || d.ip) + '" style="cursor:pointer">删除</a>' : '') }
      ];
      cells.rowAttr = 'data-pending-row="' + esc(d.ip) + '" class="' + selectedClass + '"';
      return cells;
    });
    var selectedCount = Object.keys(STATE.pendingSelected || {}).filter(function (ip) { return STATE.pendingSelected[ip]; }).length;
    var bulk = '<div class="device-bulk-bar"><div class="device-bulk-count"><b id="pdSelectedCount">' + selectedCount + '</b><span>台设备已选中</span></div>' +
      '<span class="device-bulk-hint" id="pdBulkHint">勾选已配置凭据的设备后直接采集</span><div class="btn-group">' +
      (can('ledger_write') ? '<button class="btn btn-ghost sm danger-link" id="pdBulkDelete" style="color:var(--danger)"' + (selectedCount ? '' : ' disabled') + '>批量删除</button>' : '') +
      '<button class="btn btn-ghost sm" id="pdClearSelection"' + (selectedCount ? '' : ' disabled') + '>取消选择</button></div></div>';

    var list = '<div class="card tight overview-module-card device-list-card pending-list-card">' +
      cardHead('设备清单', '', '<div class="list-search">' + (can('sync') ? '<button type="button" class="btn btn-primary sm" id="pdCollectSelected" disabled>批量采集</button>' : '') + '<label class="sr-only" for="pdSearch">搜索设备</label>' +
        textBox('pdSearch', p.keyword, '搜索 IP / 角色 / 地点') + '<button class="btn btn-ghost sm" id="pdQuery">搜索</button></div>') +
      bulk + '<div class="device-grid-wrap">' +
      (tableRows.length ? table(cols, tableRows) : emptyTable(cols, '暂无待采集设备。新增或批量导入设备后会出现在这里。')) +
      '</div>' + pagerFooter('pd', { total: data.total, page: data.page, pages: data.pages, size: data.page_size }, '条') + '</div>';

    var pendingTabs = moduleTabs([
      { key: 'pending', label: '待采集设备', icon: 'download', count: summary.total || data.total || 0 },
      { key: 'runs', label: '任务历史', icon: 'archive', count: (coll.runs || []).length },
      { key: 'logs', label: '采集日志', icon: 'file', count: (coll.last_logs || []).length },
      { key: 'settings', label: '采集设置', icon: 'settings' }
    ], pendingTab, 'pending-tab', '<span class="kpi-trend">采集操作、历史与日志均在本模块完成</span>');
    var body = pendingTab === 'pending' ? list : pageCollect(coll, true, pendingTab);
    if (coll.load_error) kpis.slice(2).forEach(function (k) { k.value = '—'; });
    if (data.credentials_error) kpis[1].value = '—';
    return head + pendingTabs + (data.load_errors || []).map(function (message) { return notice(message + '，请刷新重试。', 'danger'); }).join('') + kpiCards(kpis, true, 'pending-kpis') + body;
  }

  function openPendingBulkDeleteModal(ips) {
    if (!ips.length) { showToast('请先选择设备'); return; }
    var inner = '<div class="modal" style="width:620px"><div class="card-head"><div class="t">' +
      '<div class="title" style="font-size:18px">批量删除待采集设备</div><div class="sub">已选中 ' + ips.length + ' 台</div></div>' +
      '<button class="icon-btn" style="width:32px;height:32px" data-overlay-cancel>' + icon('close', 16) + '</button></div>' +
      notice('删除后设备会从待采集区和设备台账中移除。', 'danger') +
      '<div class="footer-bar"><span class="kpi-trend">此操作不可撤销</span><div class="btn-group">' +
      '<button class="btn btn-ghost" data-overlay-cancel>取消</button>' +
      '<button class="btn btn-primary" id="pdBulkDelConfirm" style="background:var(--danger);border-color:var(--danger)">确认删除</button></div></div></div>';
    showOverlay(inner, false);
    var btn = document.getElementById('pdBulkDelConfirm');
    if (!btn) return;
    btn.addEventListener('click', function () {
      btn.disabled = true; btn.textContent = '删除中…';
      var chain = Promise.resolve(), done = [];
      ips.forEach(function (ip) {
        chain = chain.then(function () {
          return window.NetInspect.deleteDevice(ip, true).then(function () { done.push(ip); }).catch(function () {});
        });
      });
      chain.then(function () {
        done.forEach(function (ip) { delete STATE.pendingSelected[ip]; });
        closeOverlay(); showToast('已删除 ' + done.length + ' 台待采集设备'); route();
      });
    });
  }

  function runPendingCollection(ips, withConfig) {
    ips = ips.filter(function (ip, i) { return ip && ips.indexOf(ip) === i; });
    if (STATE.pendingCollectBusy || !ips.length) return Promise.resolve();
    STATE.pendingCollectBusy = true;
    var promoted = false;
    Array.prototype.forEach.call(document.querySelectorAll('[data-pending-collect],#pdCollectSelected'), function (button) { button.disabled = true; });
    var batch = document.getElementById('pdCollectSelected');
    if (batch) batch.textContent = '采集中…';
    return window.NetInspect.collectRun({ ips: ips, with_config: !!withConfig }).then(function (res) {
      promoted = Number(res.ok || 0) > 0;
      (res.details || []).forEach(function (detail) { if (detail.ok) { delete STATE.pendingSelected[detail.ip]; delete STATE.collectSelected[detail.ip]; if (STATE.pendingDeviceCache) delete STATE.pendingDeviceCache[detail.ip]; } });
      showToast('采集完成：成功 ' + (res.ok || 0) + ' 台，失败 ' + (res.failed || 0) + ' 台；成功设备已进入设备台账');
    }).catch(function (err) { showToast('采集失败：' + err.message); }).finally(function () {
      STATE.pendingCollectBusy = false;
      if (promoted) refreshPageHash('devices', '');
      else if (key_href() === 'pending') route();
    });
  }

  function bindPending(data) {
    var p = STATE.pending;
    function credentialReadyMap() {
      var out = {};
      Object.keys(STATE.pendingDeviceCache || {}).map(function (ip) { return STATE.pendingDeviceCache[ip]; }).forEach(function (d) {
        if (d && d.ip && d.credential && d.credential.configured && !/^noip-/i.test(d.ip)) out[d.ip] = true;
      });
      return out;
    }
    function refreshChrome() {
      var ready = credentialReadyMap();
      var selected = Object.keys(STATE.pendingSelected || {}).filter(function (ip) { return STATE.pendingSelected[ip]; });
      var readyCount = selected.filter(function (ip) { return !!ready[ip]; }).length;
      var countEl = document.getElementById('pdSelectedCount'); if (countEl) { countEl.textContent = String(selected.length); countEl.closest('.device-bulk-bar').classList.toggle('has-selection', selected.length > 0); }
      var hint = document.getElementById('pdBulkHint');
      if (hint) hint.textContent = selected.length
        ? ('已选 ' + selected.length + ' 台，其中可采集 ' + readyCount + ' 台；未配凭据设备不能采集')
        : '勾选已配置凭据的设备后直接采集';
      var collectBtn = document.getElementById('pdCollectSelected');
      if (collectBtn) {
        collectBtn.disabled = selected.length === 0 || !!STATE.pendingCollectBusy || !!STATE.pendingCredentialsUnavailable;
        collectBtn.textContent = STATE.pendingCollectBusy ? '采集中…' : (selected.length ? '批量采集（' + selected.length + '）' : '批量采集');
      }
      ['pdBulkDelete', 'pdClearSelection'].forEach(function (id) { var node = document.getElementById(id); if (node) node.disabled = selected.length === 0; });
    }
    var submit = function (resetPage) {
      var keyword = document.getElementById('pdSearch'); var size = document.getElementById('pdSize');
      p.keyword = keyword ? keyword.value.trim() : '';
      p.page_size = Number(size ? size.value : 10) || 10; if (resetPage) p.page = 1;
      refreshPageHash('pending', pendingQuery());
    };
    var q = document.getElementById('pdQuery'); if (q) q.addEventListener('click', function () { submit(true); });
    var search = document.getElementById('pdSearch'); if (search) search.addEventListener('keydown', function (e) { if (e.key === 'Enter') submit(true); });
    var pageSize = document.getElementById('pdSize'); if (pageSize) pageSize.addEventListener('change', function () { submit(true); });
    var reset = document.getElementById('pdReset'); if (reset) reset.addEventListener('click', function () {
      STATE.pending = { page: 1, page_size: 10, keyword: '', sort: 'ip', order: 'asc', tab: 'pending' };
      refreshPageHash('pending', '');
    });
    bindModuleTabs('pending-tab', function (tabKey) {
      p.tab = tabKey;
      if (['runs','logs','settings'].indexOf(tabKey) >= 0) STATE.collectUi.tab = tabKey;
      refreshPageHash('pending', pendingQuery());
    });
    var prev = document.getElementById('pdPrev'); if (prev) prev.addEventListener('click', function () { if (p.page > 1) { p.page -= 1; submit(false); } });
    var next = document.getElementById('pdNext'); if (next) next.addEventListener('click', function () { p.page += 1; submit(false); });
    var all = document.getElementById('pdSelectAll'); if (all) all.addEventListener('change', function () {
      Array.prototype.forEach.call(document.querySelectorAll('[data-pending-select]'), function (box) {
        var ip = box.getAttribute('data-pending-select'); box.checked = all.checked;
        if (all.checked) STATE.pendingSelected[ip] = true; else delete STATE.pendingSelected[ip];
        var row = box.closest('tr'); if (row) row.classList.toggle('pending-row-selected', box.checked);
      }); refreshChrome();
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-pending-select]'), function (box) {
      box.addEventListener('change', function () {
        var ip = box.getAttribute('data-pending-select'); if (box.checked) STATE.pendingSelected[ip] = true; else delete STATE.pendingSelected[ip];
        var row = box.closest('tr'); if (row) row.classList.toggle('pending-row-selected', box.checked); refreshChrome();
      });
    });
    var clear = document.getElementById('pdClearSelection'); if (clear) clear.addEventListener('click', function () {
      STATE.pendingSelected = {};
      Array.prototype.forEach.call(document.querySelectorAll('[data-pending-select]'), function (box) { box.checked = false; });
      Array.prototype.forEach.call(document.querySelectorAll('[data-pending-row]'), function (row) { row.classList.remove('pending-row-selected'); }); refreshChrome();
    });
    function collectTargets(ips) {
      if (STATE.pendingCollectBusy || !ips.length || STATE.pendingCredentialsUnavailable) return;
      var ready = credentialReadyMap();
      STATE.remoteDevices = ips.map(function (ip) { return (STATE.pendingDeviceCache || {})[ip] || { ip: ip }; });
      if (ips.some(function (ip) { return !ready[ip]; })) {
        openCredentialModal(ips, false, function () { runPendingCollection(ips); });
      } else runPendingCollection(ips);
    }
    var collectSelected = document.getElementById('pdCollectSelected');
    if (collectSelected) collectSelected.addEventListener('click', function () {
      collectTargets(Object.keys(STATE.pendingSelected || {}).filter(function (ip) { return STATE.pendingSelected[ip]; }));
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-pending-collect]'), function (button) {
      button.addEventListener('click', function () { collectTargets([button.getAttribute('data-pending-collect')]); });
    });
    var bulkDelete = document.getElementById('pdBulkDelete'); if (bulkDelete) bulkDelete.addEventListener('click', function () {
      openPendingBulkDeleteModal(Object.keys(STATE.pendingSelected || {}).filter(function (ip) { return STATE.pendingSelected[ip]; }));
    });
    var add = document.getElementById('pdAdd'); if (add) add.addEventListener('click', openDeviceModal);
    var imp = document.getElementById('pdImport'); if (imp) imp.addEventListener('click', openDeviceImportModal);
    var tpl = document.getElementById('pdTemplate'); if (tpl) tpl.addEventListener('click', function () { download(window.NetInspect.base() + '/collect/device-template.csv'); });
    var refresh = document.getElementById('pdRefresh'); if (refresh) refresh.addEventListener('click', route);
    var clearHistory = document.getElementById('pdClearHistory'); if (clearHistory) clearHistory.addEventListener('click', function () {
      window.NetInspect.collectPurge(30).then(function (res) { showToast('已清理 ' + res.removed + ' 条历史日志'); route(); })
        .catch(function (err) { showToast('清理失败：' + err.message); });
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-pending-cred]'), function (link) {
      link.addEventListener('click', function () { STATE.remoteDevices = data.rows || []; openCredentialModal(link.getAttribute('data-pending-cred')); });
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-pending-delete]'), function (link) {
      link.addEventListener('click', function () {
        openDeleteDeviceModal(link.getAttribute('data-pending-delete'), link.getAttribute('data-pending-name'), function (ips) {
          ips.forEach(function (ip) { delete STATE.pendingSelected[ip]; }); route();
        });
      });
    });
    if (data.collect) bindCollect(data.collect, true);
    refreshChrome();
  }

  /* ---------- 台账批量导入（实景：几十上百台设备一次补齐资产编号/责任人/用途） ---------- */
  function openDeviceModal() {
    var inner =
      '<div class="modal" style="width:680px">' +
      '<div class="card-head" style="margin-bottom:14px"><div class="t">' +
      '<div class="title" style="font-size:18px">新增待采集设备</div>' +
      '<div class="sub">保存后先进入待采集区；配置凭据并采集成功且在线后，自动转入设备台账</div></div>' +
      '<button class="icon-btn" id="devClose" style="width:32px;height:32px">' + icon('close', 16) + '</button></div>' +
      '<div class="form-row">' + field('序列号', plainBox('dSerial', '')) + field('设备角色', plainBox('dRole', '')) + '</div>' +
      '<div class="form-row">' + field('管理 IP *', plainBox('dIp', '')) + field('设备地点', plainBox('dLocation', '')) + '</div>' +
      notice('IP 为必填；角色和地点会保留到设备台账，名称、型号、版本等由采集回填。', '') +
      '<div id="devResult"></div>' +
      '<div class="footer-bar"><span class="kpi-trend">只读采集：仅执行 display 类命令，不做任何配置变更</span>' +
      '<div class="btn-group"><button class="btn btn-ghost" id="devCancel">取消</button>' +
      '<button class="btn btn-primary" id="devSave">保存</button></div></div></div>';
    showOverlay(inner, false);
    var save = document.getElementById('devSave');
    if (save) save.addEventListener('click', function () {
      var ip = (document.getElementById('dIp') || {}).value || '';
      if (!ip.trim()) { showToast('请填写管理 IP'); return; }
      var payload = {
        ip: ip.trim(),
        serial: (document.getElementById('dSerial') || {}).value || '',
        role: (document.getElementById('dRole') || {}).value || '',
        port: 22,
        vendor: ''
      };
      var ledger = { location: (document.getElementById('dLocation') || {}).value || '' };
      save.textContent = '保存中…';
      window.NetInspect.createDevice(payload).then(function () {
        var hasLedger = Object.keys(ledger).some(function (key) { return String(ledger[key] || '').trim(); });
        return hasLedger ? window.NetInspect.saveLedger(payload.ip, ledger) : null;
      }).then(function () {
        closeOverlay();
        STATE.pending.tab = 'pending';
        STATE.pending.page = 1;
        showToast('设备已加入待采集，请配置凭据并测试连接');
        refreshPageHash('pending', pendingQuery());
      }).catch(function (err) {
        save.textContent = '保存';
        document.getElementById('devResult').innerHTML = notice(err.message, 'danger');
      });
    });
  }

  /* ---------- 批量导入设备弹窗 ---------- */
  function openDeviceImportModal() {
    var inner =
      '<div class="modal" style="width:820px">' +
      '<div class="card-head" style="margin-bottom:14px"><div class="t">' +
      '<div class="title" style="font-size:18px">批量导入待采集设备</div>' +
      '<div class="sub">仅需四列：序列号、设备角色、IP地址、设备地点；IP地址为必填</div></div>' +
      '<button class="icon-btn" id="diClose" style="width:32px;height:32px">' + icon('close', 16) + '</button></div>' +
      '<div class="summary-bar"><div class="avatar">' + icon('server', 18) + '</div>' +
      '<div class="info"><span class="n">示例</span>' +
      '<span class="m">序列号,设备角色,IP地址,设备地点 / LAB-SW-001,核心交换机,10.10.9.1,信息中心机房</span></div></div>' +
      notice('角色和地点随设备保留；设备名称、型号、版本、在线状态等由采集回填。', '') +
      '<div class="form-row">' +
      '<div class="field" style="flex:1"><label>选择 CSV 文件（或直接粘贴）</label>' +
      '<div class="input" style="height:38px"><input id="diFile" type="file" accept=".csv,.txt,text/csv" style="' + CTRL + '"/></div></div>' +
      '<div class="field" style="width:210px"><label>执行方式</label>' +
      picker('diMode', [{ value: 'dry', label: '仅预检（不写库）' }, { value: 'apply', label: '写入待采集' }], 'dry') +
      '</div></div>' +
      '<div class="field"><label>CSV 内容</label>' +
      '<div class="input" style="height:auto;padding:8px 12px"><textarea id="diText" rows="8" style="' + CTRL + ';resize:vertical;font-family:var(--font-mono);font-size:12px"></textarea></div></div>' +
      '<div id="diResult"></div>' +
      '<div class="footer-bar"><span class="kpi-trend">导入后在设备采集中心补凭据并执行采集，成功且在线后自动转入设备台账</span>' +
      '<div class="btn-group"><button class="btn btn-ghost" id="diCancel">关闭</button>' +
      '<button class="btn btn-primary" id="diSave">开始导入</button></div></div></div>';
    showOverlay(inner, false);
    var file = document.getElementById('diFile');
    if (file) file.addEventListener('change', function () {
      var f = file.files && file.files[0];
      if (!f) return;
      var reader = new FileReader();
      reader.onload = function () { document.getElementById('diText').value = String(reader.result || ''); };
      reader.readAsText(f, 'utf-8');
    });
    var save = document.getElementById('diSave');
    if (save) save.addEventListener('click', function () {
      var text = (document.getElementById('diText') || {}).value || '';
      if (!text.trim()) { showToast('请先选择文件或粘贴 CSV'); return; }
      var dryRun = (document.getElementById('diMode') || {}).value !== 'apply';
      save.textContent = dryRun ? '预检中…' : '导入中…';
      window.NetInspect.importDevices(text, dryRun).then(function (res) {
        save.textContent = '开始导入';
        var head = dryRun
          ? ('预检完成：将新增 ' + (res.details || []).filter(function (d) { return d.action === 'would_create'; }).length
             + ' 台、更新 ' + (res.details || []).filter(function (d) { return d.action === 'would_update'; }).length
             + ' 台、报错 ' + res.error_count + ' 行（未写库）')
          : ('导入完成：新增 ' + res.created + ' 台、更新 ' + res.updated + ' 台、报错 ' + res.error_count + ' 行');
        var rows = (res.details || []).map(function (d) {
          var tone = d.action === 'error' ? 'danger'
            : (d.action === 'create' || d.action === 'would_create') ? 'success'
            : (d.action === 'update' || d.action === 'would_update') ? 'brand' : 'neutral';
          var label = { create: '新增', update: '更新', would_create: '将新增',
                        would_update: '将更新', error: '报错' }[d.action] || d.action;
          return [{ text: String(d.line), cls: 'dim mono' }, { text: d.ip || '—', cls: 'mono' },
                  { html: tag(label, tone) }, { text: d.message || '' }];
        });
        var cols = [{ text: '行', width: 60 }, { text: 'IP 地址', width: 150 },
          { text: '结果', width: 90 }, { text: '说明' }];
        document.getElementById('diResult').innerHTML = notice(head, res.error_count ? 'danger' : '') +
          '<div style="max-height:240px;overflow:auto;margin-top:10px">' +
          (rows.length ? table(cols, rows) : emptyTable(cols, '没有可处理的记录')) + '</div>';
        if (!dryRun && (res.created + res.updated) > 0) {
          showToast('设备台账已导入：新增 ' + res.created + ' / 更新 ' + res.updated);
          STATE.refreshAfterOverlay = true;
        }
      }).catch(function (err) {
        save.textContent = '开始导入';
        document.getElementById('diResult').innerHTML = notice('导入失败：' + err.message, 'danger');
      });
    });
  }

  /* ---------- 页面：03 服务器健康检查 / 04 交换机健康检查 ---------- */
  function deviceSelector(data, id, exportKind, extra) {
    var pool = data.pool || [], dev = data.device || {};
    var options = pool.map(function (d) { return { value: d.id, label: d.name + '（' + d.ip + '）' }; });
    return '<section class="health-toolbar" aria-label="当前设备"><div class="health-picker">' +
      field('当前设备', picker(id, options, dev.id, pool.length ? '' : '暂无可选设备')) + '</div>' +
      '<div class="health-context">' + tag(dev.health_label || '未巡检', dev.health_tone || 'neutral') +
      '<span>最近巡检 ' + esc(dev.last_inspected_text || '尚未巡检') + '</span></div>' +
      '<div class="health-actions">' + (extra || '') + '<button type="button" class="btn btn-ghost sm" id="' + id + 'Remote">远程控制台</button>' +
      '<details class="health-export"><summary>导出报告</summary><div class="health-report-menu">' +
      [{key:'Export',label:'CSV 明细'},{key:'Pdf',label:'PDF 检查报告'},{key:'Report',label:'Word 检查报告'}].map(function (item) {
        return '<button type="button" id="' + id + item.key + '">' + esc(item.label) + '</button>';
      }).join('') + '</div></details></div></section>';
  }

  function healthEmptyState(label, pool, kind) {
    if (pool && pool.length) return '<div class="card health-empty"><div class="title">所选设备不在当前分类中</div><p>设备可能已移除，或链接指向了其他设备分类。</p><a class="btn btn-primary sm" href="#/' + kind + '">查看' + esc(label) + '设备</a></div>';
    return '<div class="card health-empty"><div class="title">暂无可用的' + esc(label) + '巡检数据</div>' +
      '<p>请在设备采集页添加设备并完成采集，成功后会进入台账和健康检查。</p><a class="btn btn-primary sm" href="#/pending">前往设备采集</a></div>';
  }

  function openHealthBatchReport(kind, pool, currentId) {
    pool = (pool || []).slice();
    if (!pool.length) { showToast('当前分类没有可生成报告的设备'); return; }
    var typeLabel = kind === 'server' ? '服务器' : (kind === 'security' ? '安全设备' : '交换机');
    var selected = {};
    if (currentId) selected[String(currentId)] = true;

    var rows = pool.map(function (d) {
      var key = String(d.id);
      var searchText = [d.name, d.ip, d.model, d.type_label, d.group].filter(Boolean).join(' ').toLowerCase();
      var tone = d.health_tone || 'neutral';
      return '<label class="batch-device-row" data-hr-row data-search="' + esc(searchText) + '" data-tone="' + esc(tone) + '">' +
        '<input type="checkbox" data-hr-device="' + esc(key) + '"' + (selected[key] ? ' checked' : '') + '/>' +
        '<span class="batch-device-main"><b>' + esc(d.name || d.ip || '—') + '</b>' +
        '<small>' + esc(d.type_label || typeLabel) + ' · ' + esc(d.ip || '未配置管理 IP') + (d.model ? ' · ' + esc(d.model) : '') + '</small></span>' +
        '<span class="batch-device-health">' + tag(d.health_label || '未巡检', tone) + '</span>' +
        '<span class="batch-device-time">' + esc(d.last_inspected_text || '尚未巡检') + '</span></label>';
    }).join('');

    var inner = '<div class="modal batch-report-modal">' +
      '<div class="card-head"><div class="t"><div class="title" style="font-size:18px">' + esc(typeLabel) + '合并健康性检查报告</div>' +
      '<div class="sub">可多选或全选当前分类设备，所选设备按顺序写入同一份 Word / PDF 文档</div></div>' +
      '<button class="icon-btn" style="width:32px;height:32px" data-overlay-cancel>' + icon('close', 16) + '</button></div>' +
      '<div class="batch-report-toolbar">' +
      '<div class="batch-report-search">' + textBox('hrSearch', '', '搜索设备名称 / IP / 型号') + '</div>' +
      '<label class="batch-report-format"><span>报告格式</span><select id="hrFormat" class="grid-filter-select">' +
      '<option value="docx">Word（.docx）</option><option value="pdf">PDF（.pdf）</option></select></label>' +
      '<div class="btn-group batch-report-quick">' +
      '<button class="btn btn-ghost sm" id="hrAll">全选全部</button>' +
      '<button class="btn btn-ghost sm" id="hrAbnormal">仅选异常</button>' +
      '<button class="btn btn-ghost sm" id="hrClear">清空</button></div>' +
      '<span class="batch-report-count" id="hrCount">已选 0 台</span></div>' +
      '<div class="batch-device-list" id="hrList">' + rows + '</div>' +
      '<div class="footer-bar"><span class="kpi-trend">生成一份合并报告；设备越多生成时间越长，下载过程中可取消</span>' +
      '<div class="btn-group"><button class="btn btn-ghost" data-overlay-cancel>取消</button>' +
      '<button class="btn btn-primary" id="hrGenerate">生成合并报告</button></div></div></div>';
    showOverlay(inner, false);

    var countEl = document.getElementById('hrCount');
    var generate = document.getElementById('hrGenerate');
    var search = document.getElementById('hrSearch');
    var boxes = Array.prototype.slice.call(document.querySelectorAll('[data-hr-device]'));
    var chosen = function () { return boxes.filter(function (box) { return box.checked; }); };
    function update() {
      boxes.forEach(function (box) {
        var row = box.closest('[data-hr-row]');
        if (row) row.classList.toggle('selected', box.checked);
      });
      var count = chosen().length;
      if (countEl) countEl.textContent = '已选 ' + count + ' 台 / 共 ' + pool.length + ' 台';
      if (generate) {
        generate.disabled = count === 0;
        generate.textContent = count ? ('生成合并报告（' + count + ' 台）') : '请选择设备';
      }
    }
    boxes.forEach(function (box) { box.addEventListener('change', update); });
    if (search) search.addEventListener('input', function () {
      var q = search.value.trim().toLowerCase();
      Array.prototype.forEach.call(document.querySelectorAll('[data-hr-row]'), function (row) {
        row.hidden = !!q && (row.getAttribute('data-search') || '').indexOf(q) < 0;
      });
    });
    var all = document.getElementById('hrAll');
    if (all) all.addEventListener('click', function () { boxes.forEach(function (box) { box.checked = true; }); update(); });
    var abnormal = document.getElementById('hrAbnormal');
    if (abnormal) abnormal.addEventListener('click', function () {
      boxes.forEach(function (box) {
        var row = box.closest('[data-hr-row]');
        box.checked = !!row && row.getAttribute('data-tone') !== 'success';
      });
      update();
    });
    var clear = document.getElementById('hrClear');
    if (clear) clear.addEventListener('click', function () { boxes.forEach(function (box) { box.checked = false; }); update(); });
    if (generate) generate.addEventListener('click', function () {
      var ids = chosen().map(function (box) { return box.getAttribute('data-hr-device'); });
      if (!ids.length) { showToast('请至少选择一台设备'); return; }
      var fmtEl = document.getElementById('hrFormat');
      var fmt = fmtEl ? fmtEl.value : 'docx';
      closeOverlay();
      download(window.NetInspect.exportUrl({
        kind: kind, format: fmt, device: ids.join(','), hours: 24 * 30
      }), {
        label: typeLabel + '合并健康性检查报告', ext: fmt, progress: true,
        after: function () { setTimeout(route, 600); }
      });
    });
    update();
  }

  function pageServer(data) {
    var dev = data.device || {};
    var head =
      topbar('搜索设备名称 / IP 地址 / 报告编号') +
      '<div class="page-head"><div class="page-title"><h1>服务器健康性检查</h1>' +
      '<div class="page-sub"><span>设备角色：' + esc(dev.role || dev.type_label || '—') + '</span></div></div>' +
      '<div class="cta-row"><button class="btn btn-primary" id="svBatchTop">批量报告</button>' +
      '<button class="btn btn-ghost" id="svRefresh">' + icon('refresh', 14) + '刷新</button></div></div>';

    if (!dev.id) {
      return head + healthEmptyState('服务器', data.pool, 'server');
    }

    var basic = '<div class="card health-basic">' + cardHead('基本信息', '', '') +
      '<div class="form-row">' + (data.basic || []).slice(0, 3).map(function (b) {
        return field(b.label, input(b.value));
      }).join('') + '</div>' +
      '<div class="form-row">' + (data.basic || []).slice(3, 6).map(function (b) {
        return field(b.label, input(b.value));
      }).join('') + '</div>' +
      '<div class="form-row">' + (data.basic || []).slice(6, 9).map(function (b) {
        return field(b.label, input(b.value, b.label === 'IP 地址'));
      }).join('') + '</div></div>';

    var serverTab = ['checks', 'resources', 'environment', 'channels', 'advice'].indexOf(STATE.serverTab) >= 0 ? STATE.serverTab : 'checks';
    var abnormal = (data.checks || []).filter(function (c) { return c.tone !== 'success'; }).length;
    var serverTabs = moduleTabs([
      { key: 'checks', label: '检查项结果', icon: 'file', count: (data.checks || []).length },
      { key: 'resources', label: '资源使用率', icon: 'cpu' },
      { key: 'environment', label: '机房环境', icon: 'gauge' },
      { key: 'channels', label: '采集通道', icon: 'network' },
      { key: 'advice', label: '维护建议', icon: 'alert', count: (data.advice || []).length }
    ], serverTab, 'server-tab', '<span class="kpi-trend">' + (abnormal ? abnormal + ' 项需关注' : '全部检查通过') + '</span>');
    var checks = '<div class="card">' + cardHead('检查项结果',
      '共 ' + (data.checks || []).length + ' 项 · ' + ((data.checks || []).length ? (abnormal ? abnormal + ' 项需关注' : '全部通过') : '暂无检查结果'), '') +
      '<div style="overflow-x:auto">' + table(
        [{ text: '检查项目', width: 220 }, { text: '检查结果', width: 140 }, { text: '说明 / 异常记录' }],
        (data.checks || []).map(function (c) {
          return [
            { text: c.item, cls: 'strong' },
            { html: tag(c.result, c.tone === 'success' ? 'success' : c.tone === 'danger' ? 'danger' : c.tone === 'warning' ? 'warning' : 'neutral') },
            { text: c.note }
          ];
        })
      ) + '</div></div>';

    var resources = '<div class="card">' + cardHead('资源使用率', '最近一次采集', '') + statList(data.resources || []) + '</div>';
    var environment = '<div class="card">' + cardHead('机房环境巡检', '', '') + statList(data.environment || []) + '</div>';
    var applications = '<div class="card">' + cardHead('采集通道巡检', '', '') + statList(data.applications || []) + '</div>';
    var advice = '<div class="card">' + cardHead('维护建议', '', '') + statList((data.advice || []).map(function (t, i) {
      return { name: (i + 1) + '. ', value: t };
    })) + '</div>';
    var body;
    if (serverTab === 'resources') body = resources;
    else if (serverTab === 'environment') body = environment;
    else if (serverTab === 'channels') body = applications;
    else if (serverTab === 'advice') body = advice;
    else body = basic + checks;

    return head + sourceNotice(data.source_info, data.source) + deviceSelector(data, 'svDevice', 'server') + serverTabs + body;
  }

  function pageSwitch(data, kind) {
    var dev = data.device || {};
    var security = kind === 'security';
    var allowedTabs = security ? ['checks', 'perf', 'advice'] : ['checks', 'lldp', 'perf', 'advice'];
    var tab = allowedTabs.indexOf(STATE.switchTab) >= 0 ? STATE.switchTab : 'checks';
    var head =
      topbar('搜索设备名称 / IP / 责任人 / 告警') +
      '<div class="page-head"><div class="page-title"><h1>' + (security ? '安全设备健康性检查' : '内网交换机健康性检查') + '</h1>' +
      '<div class="page-sub"><span>设备角色：' + esc(dev.role || dev.type_label || '—') + '</span></div></div>' +
      '<div class="cta-row"><button class="btn btn-primary" id="swBatchTop">批量报告</button>' +
      '<button class="btn btn-ghost" id="swRefresh">' + icon('refresh', 14) + '刷新</button></div></div>';

    if (!dev.id) {
      return head + healthEmptyState(security ? '安全设备' : '网络设备', data.pool, kind || 'switch');
    }

    var neighbors = data.neighbors || [];
    var checks = data.checks || [];
    var abnormal = checks.filter(function (c) { return c.tone !== 'success'; }).length;
    var tabItems = [
      { key: 'checks', label: '检查详情', icon: 'file', count: checks.length }
    ];
    if (!security) tabItems.push({ key: 'lldp', label: 'LLDP 邻居', icon: 'network', count: neighbors.length });
    tabItems.push({ key: 'perf', label: '性能与运行状态', icon: 'cpu' });
    tabItems.push({ key: 'advice', label: '维护建议', icon: 'alert', count: (data.advice || []).length });
    var tabs = moduleTabs(tabItems, tab, 'tab',
      '<span class="kpi-trend">健康度 ' + esc(dev.health_score === null || dev.health_score === undefined ? '—' : dev.health_score) +
      ' · ' + (checks.length ? (abnormal ? abnormal + ' 项需关注' : '全部正常') : '暂无检查结果') + '</span>');

    var basic = '<div class="card health-basic">' + cardHead('设备信息', '', '') +
      '<div class="form-row">' + (data.basic || []).slice(0, 3).map(function (b) {
        return field(b.label, input(b.value, b.label === 'IP 地址'));
      }).join('') + '</div>' +
      '<div class="form-row">' + (data.basic || []).slice(3, 6).map(function (b) {
        return field(b.label, input(b.value));
      }).join('') + '</div></div>';

    var checksCard = '<div class="card">' + cardHead('检查详细情况',
      '共 ' + checks.length + ' 项检查 · ' + (abnormal ? abnormal + ' 项需关注' : '全部正常'), '') +
      '<div style="overflow-x:auto">' + table(
        [{ text: '检查项', width: 180 }, { text: '检查方式命令', width: 210 }, { text: '检查目的', width: 320 }, { text: '检查结果', width: 120 }],
        checks.map(function (c) {
          return [
            { text: c.item, cls: 'strong' },
            { text: c.cmd || '—', cls: 'mono' },
            { text: c.purpose || '' },
            { html: tag(c.result, c.tone === 'success' ? 'success' : c.tone === 'danger' ? 'danger' : c.tone === 'warning' ? 'warning' : 'neutral') }
          ];
        })) + '</div></div>';

    var lldpCard = '<div class="card">' + cardHead('LLDP 邻居', '本平台 display lldp neighbor 采集结果（未登记的邻居说明台账还没录它）', '') +
      '<div style="overflow-x:auto">' + (neighbors.length ? table(
        [{ text: '本端端口', width: 160 }, { text: '邻居设备', width: 220 }, { text: '邻居端口', width: 160 }, { text: '邻居 IP' }, { text: '台账' }],
        neighbors.map(function (n) {
          return [
            { text: n.local_port, cls: 'mono' },
            { text: n.neighbor_name || '—', cls: 'strong' },
            { text: n.neighbor_port || '—', cls: 'mono' },
            { text: n.neighbor_ip || '—', cls: 'mono' },
            { html: (n.known_device || n.known) ? '<a href="#/devices?ip=' + encodeURIComponent(n.known_device_ip || n.neighbor_ip || '') + '">' + tag('已登记', 'success') + '</a>' : tag('未登记', 'neutral') }
          ];
        })) : emptyTable([{ text: '本端端口' }, { text: '邻居设备' }, { text: '邻居端口' }, { text: '邻居 IP' }, { text: '台账' }],
          '该设备还没有 LLDP 邻居数据（采集未取到或确实没有邻居）')) + '</div></div>';

    var perfCard = '<div class="card">' + cardHead('性能与运行状态', '来自本平台巡检采集', '') +
      '<div class="form-row">' +
      '<div style="flex:1">' + statList(data.performance || []) + '</div>' +
      '<div style="flex:1"><div class="stat-list">' + (data.status_rows || []).map(function (l) {
        return '<div class="stat-item"><span class="n">' + esc(l.name) + '</span>' +
          '<span class="status-text ' + toneClass(l.tone) + '">' + esc(l.value) + '</span></div>';
      }).join('') + '</div></div></div></div>';

    var adviceCard = '<div class="card">' + cardHead('维护建议', '根据当前巡检结论生成', '') +
      statList((data.advice || []).map(function (t, i) {
        return { name: (i + 1) + '. ', value: t };
      })) + '</div>';
    var body;
    if (tab === 'lldp') body = lldpCard;
    else if (tab === 'perf') body = perfCard;
    else if (tab === 'advice') body = adviceCard;
    else body = basic + checksCard;

    return head + sourceNotice(data.source_info, data.source) + deviceSelector(data, 'swDevice', kind || 'switch') + tabs + body;
  }

  function pageSecurity(data) { return pageSwitch(data, 'security'); }

  function bindHealth(page, id, data) {
    Array.prototype.forEach.call(document.querySelectorAll('[data-tab]'), function (chip) {
      chip.addEventListener('click', function () {
        refreshPageHash(page, 'device=' + encodeURIComponent((data.device || {}).ip || '') + '&tab=' + encodeURIComponent(chip.getAttribute('data-tab')));
      });
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-server-tab]'), function (tab) {
      tab.addEventListener('click', function () {
        refreshPageHash(page, 'device=' + encodeURIComponent((data.device || {}).ip || '') + '&tab=' + encodeURIComponent(tab.getAttribute('data-server-tab')));
      });
    });
    var kind = page === 'server' ? 'server' : (page === 'security' ? 'security' : 'switch');
    var healthData = data || {};
    var openBatch = function () {
      openHealthBatchReport(kind, healthData.pool || [], (healthData.device || {}).id);
    };
    var batchButton = document.getElementById(page === 'server' ? 'svBatchTop' : 'swBatchTop');
    if (batchButton) batchButton.addEventListener('click', openBatch);
    var sel = document.getElementById(id);
    if (sel) sel.addEventListener('change', function () {
      if (sel.value) refreshPageHash(page, 'device=' + encodeURIComponent(sel.value) + '&tab=' + encodeURIComponent(page === 'server' ? STATE.serverTab : STATE.switchTab));
    });
    var refresh = document.getElementById(page === 'server' ? 'svRefresh' : 'swRefresh');
    if (refresh) refresh.addEventListener('click', route);
    var remoteJump = document.getElementById(id + 'Remote');
    if (remoteJump) remoteJump.addEventListener('click', function () {
      var node = document.getElementById(id);
      if (!node || !node.value) { showToast('请先选择设备'); return; }
      var selected = (healthData.pool || []).filter(function (d) { return String(d.id) === String(node.value); })[0] || healthData.device || {};
      if (!selected.ip) { showToast('无法识别设备 IP，请刷新后重试'); return; }
      STATE.remote.ip = selected.ip;
      location.hash = '#/console?category=' + (kind === 'security' ? 'security' : (kind === 'server' ? 'server' : 'switch')) + '&device=' + encodeURIComponent(STATE.remote.ip);
    });
    // 页头按钮（生成报告）+ 设备卡片里的「导出该设备报表 / 生成检查报告」
    var targets = [
      { id: id + 'Report', format: 'docx', label: 'Word 版式报告' },
      { id: id + 'Pdf', format: 'pdf', label: 'PDF 版式报告' },
      { id: id + 'Export', format: 'csv', label: 'CSV 报表' }
    ];
    targets.forEach(function (target) {
      var btn = document.getElementById(target.id);
      if (!btn) return;
      btn.addEventListener('click', function () {
        var picked = document.getElementById(id);
        var isDoc = target.format === 'docx' || target.format === 'pdf';
        download(window.NetInspect.exportUrl({
          kind: kind, format: target.format, device: picked ? picked.value : ''
        }), { label: target.label, ext: target.format });
        if (isDoc) setTimeout(route, 4000);
      });
    });
  }
  /* ---------- 页面：聚合告警 ---------- */
  function applyAlertsQuery(query) {
    var a = STATE.alerts;
    if (!a) return;
    a.hours = Number(query.hours) || 168;
    a.severity = query.severity || '';
    a.status = query.status || '';
    a.keyword = query.keyword || '';
    a.device = query.device || '';
    a.page = Number(query.page || 1) || 1;
    a.page_size = Number(query.page_size || 10) || 10;
  }

  function alertQuery() {
    var a = STATE.alerts || {};
    var parts = [];
    if (a.hours && Number(a.hours) !== 168) parts.push('hours=' + encodeURIComponent(a.hours));
    if (a.severity) parts.push('severity=' + encodeURIComponent(a.severity));
    if (a.status) parts.push('status=' + encodeURIComponent(a.status));
    if (a.keyword) parts.push('keyword=' + encodeURIComponent(a.keyword));
    if (a.device) parts.push('device=' + encodeURIComponent(a.device));
    if (Number(a.page) > 1) parts.push('page=' + Number(a.page));
    if (Number(a.page_size) !== 10) parts.push('page_size=' + Number(a.page_size));
    return parts.join('&');
  }

  function alertSeverityTone(sev) {
    return sev === 'critical' || sev === 'major' ? 'danger' : (sev === 'warning' ? 'warning' : 'neutral');
  }

  function openAlertGroup(key) {
    var group = (STATE.alertGroups || []).filter(function (g) { return g.key === key; })[0];
    if (!group) return;
    var inner = '<div class="drawer" style="width:760px">' +
      '<div class="card-head"><div class="t"><div class="title" style="font-size:18px">' + esc(group.title || '聚合告警') + '</div>' +
      '<div class="sub">' + esc(group.device || group.device_ip || '') + ' · ' + esc(group.metric || '') +
      ' · 共 ' + esc(group.count || 0) + ' 次 · 影响对象 ' + esc(group.resource_count || 0) + ' 个</div></div>' +
      '<button class="icon-btn" style="width:32px;height:32px" data-overlay-cancel>' + icon('close', 16) + '</button></div>' +
      '<div class="split"><div class="col-main">' +
      '<div class="card tight">' + cardHead('收敛摘要', '', tag(group.severity_label || '', alertSeverityTone(group.severity))) +
      statList([
        { name: '设备', value: group.device || group.device_ip || '—' },
        { name: '指标族', value: group.metric || group.family || '—' },
        { name: '首次出现', value: group.first_time || '—' },
        { name: '最近出现', value: group.last_time || '—' },
        { name: '累计次数', value: String(group.count || 0) },
        { name: '影响对象', value: String(group.resource_count || 0) },
        { name: '状态', value: group.open ? '未恢复' : (group.status || '—') }
      ]) + '</div>' +
      '<div class="card tight">' + cardHead('最近原始告警', '最多展示 6 条，完整记录可在告警报表中查看', '') +
      '<div class="stat-list">' + (group.recent || []).map(function (r) {
        return '<div class="stat-item" style="height:auto;padding:10px 0;flex-direction:column;align-items:flex-start;gap:4px;border-bottom:1px solid var(--border)">' +
          '<span style="color:var(--text-1);white-space:normal">' + esc(r.content || '') + '</span>' +
          '<span class="kpi-trend">' + esc(r.time || '') + ' · ' + esc(r.severity || '') + ' · ' + esc(r.status || '') + '</span></div>';
      }).join('') + '</div></div></div>' +
      '<div class="col-side"></div></div>' +
      '<div class="footer-bar"><span class="kpi-trend">聚合规则：同一设备 + 同一指标族；最高级别和未恢复状态优先</span>' +
      '<div class="btn-group"><button class="btn btn-ghost" data-overlay-cancel>关闭</button></div></div></div>';
    showOverlay(inner, true);
  }

  function openAlertDisposition(group) {
    if (!group || !(group.alert_ids || []).length) { showToast('该分组没有可处置的原始告警'); return; }
    var inner = '<div class="modal" style="width:560px">' +
      '<div class="card-head"><div class="t"><div class="title" style="font-size:18px">告警处置</div>' +
      '<div class="sub">' + esc(group.device || group.device_ip || '') + ' · ' + esc(group.metric || group.family || '') + '</div></div>' +
      '<button class="icon-btn" style="width:32px;height:32px" data-overlay-cancel>' + icon('close', 16) + '</button></div>' +
      field('处置状态', picker('adStatus', [
        { value: 'acknowledged', label: '已确认' },
        { value: 'resolved', label: '已恢复' },
        { value: 'closed', label: '已关闭' },
        { value: 'new', label: '重新打开' }
      ], group.open ? 'acknowledged' : 'closed')) +
      field('责任人', plainBox('adAssignee', '')) +
      '<div class="field"><label>处置备注</label><div class="input" style="height:auto;padding:8px 12px">' +
      '<textarea id="adNote" rows="4" placeholder="填写处理过程、恢复情况或关闭原因" style="' + CTRL + ';resize:vertical"></textarea></div></div>' +
      '<div class="footer-bar"><span class="kpi-trend">本次将更新 ' + (group.alert_ids || []).length + ' 条原始告警，并写入审计</span>' +
      '<div class="btn-group"><button class="btn btn-ghost" data-overlay-cancel>取消</button>' +
      '<button class="btn btn-primary" id="adSave">确认处置</button></div></div></div>';
    showOverlay(inner, false);
    var save = document.getElementById('adSave');
    if (save) save.addEventListener('click', function () {
      save.textContent = '提交中…';
      window.NetInspect.disposeAlerts(
        group.alert_ids,
        (document.getElementById('adStatus') || {}).value || 'acknowledged',
        (document.getElementById('adAssignee') || {}).value || '',
        (document.getElementById('adNote') || {}).value || ''
      ).then(function (res) {
        closeOverlay();
        showToast('已处置 ' + (res.changed || 0) + ' 条告警');
        route();
      }).catch(function (err) {
        save.textContent = '确认处置';
        showToast('处置失败：' + err.message);
      });
    });
  }

  function pageAlerts(data) {
    var a = STATE.alerts || {};
    var groups = data.groups || [];
    var raw = Number(data.raw_total || 0);
    var groupTotal = Number(data.group_total || 0);
    var collapsed = Number(data.collapsed || 0);
    var collapseRate = Number(data.collapse_rate || 0);
    var openGroups = groups.filter(function (g) { return g.open; }).length;
    var alertTab = ['list', 'severity', 'devices'].indexOf(a.tab) >= 0 ? a.tab : 'list';
    var alertTabs = moduleTabs([
      { key: 'list', label: '告警列表', icon: 'alert', count: groupTotal },
      { key: 'severity', label: '级别与状态', icon: 'list', count: groupTotal },
      { key: 'devices', label: '设备排行', icon: 'server', count: (data.by_device || []).length }
    ], alertTab, 'alert-tab', '<span class="kpi-trend">列表、级别状态与设备排行独立查看</span>');
    var pageSize = [10, 20, 50].indexOf(Number(a.page_size)) >= 0 ? Number(a.page_size) : 10;
    var totalPages = Math.max(1, Math.ceil(groups.length / pageSize));
    var pageNo = Math.max(1, Math.min(Number(a.page) || 1, totalPages));
    a.page_size = pageSize;
    a.page = pageNo;
    var start = (pageNo - 1) * pageSize;
    var pagedGroups = groups.slice(start, start + pageSize);
    STATE.alertGroups = pagedGroups;
    var head = topbar('搜索设备 / IP / 告警内容 / 指标') +
      '<div class="page-head"><div class="page-title"><h1>聚合告警</h1>' +
      '<div class="page-sub"><span>原始告警 ' + raw + ' 条 → 聚合 ' + groupTotal + ' 组 · 收敛 ' + collapsed + ' 条（' + collapseRate + '%）</span>' +
      '<span>同设备、同指标族自动收敛，保留最高级别与最近状态</span></div></div>' +
      '<div class="cta-row"><button class="btn btn-ghost" id="alExport">导出告警报表</button>' +
      '<button class="btn btn-primary" id="alRefresh">' + icon('refresh', 14) + '刷新</button></div></div>';
    var kpis = [
      { label: '原始告警', value: String(raw), unit: '条', note: '所选区间与筛选条件下', tone: 'default' },
      { label: '聚合后', value: String(groupTotal), unit: '组', note: '每台设备每个指标族一组', tone: groupTotal ? 'success' : 'muted' },
      { label: '已收敛', value: String(collapsed), unit: '条', note: collapseRate + '% 噪声被合并', tone: collapsed ? 'success' : 'muted' },
      { label: '未恢复分组', value: String(openGroups), unit: '组', note: '优先显示在最前面', tone: openGroups ? 'warning' : 'success' }
    ];
    var filter = '<div class="module-filter-block"><div class="form-row module-filter-row">' +
      field('时间范围', picker('alHours', [{ value: '24', label: '近 1 天' }, { value: '168', label: '近 7 天' },
        { value: '720', label: '近 30 天' }, { value: '2160', label: '近 90 天' }], String(a.hours || 168))) +
      field('级别', picker('alSeverity', [{ value: '', label: '全部级别' }, { value: 'critical', label: '紧急' },
        { value: 'major', label: '严重' }, { value: 'warning', label: '警告' }, { value: 'info', label: '提示' }], a.severity || '')) +
      field('状态', picker('alStatus', [{ value: '', label: '全部状态' }, { value: 'new', label: '未处理' },
        { value: 'acknowledged', label: '已确认' }, { value: 'resolved', label: '已恢复' },
        { value: 'closed', label: '已关闭' }], a.status || '')) +
      field('设备 / IP', plainBox('alDevice', a.device || '')) +
      field('关键字', textBox('alKeyword', a.keyword || '', '告警内容 / 指标 / 设备')) +
      '</div><div class="btn-group" style="justify-content:flex-end">' +
      '<button class="btn btn-ghost sm" id="alReset">重置</button>' +
      '<button class="btn btn-primary sm" id="alQuery">查询</button></div></div>';
    var cols = [{ text: '级别', width: 84 }, { text: '设备', width: 170 },
      { text: '指标族', width: 130 }, { text: '聚合内容', width: 320 },
      { text: '次数', width: 70 }, { text: '对象', width: 70 },
      { text: '首次 / 最近', width: 190 }, { text: '状态', width: 90 },
      { text: '操作', width: 150 }];
    var rows = pagedGroups.map(function (g) {
      return [
        { html: tag(g.severity_label || '', alertSeverityTone(g.severity)) },
        { html: '<span class="strong">' + esc(g.device || g.device_ip || '—') + '</span><br/><span class="kpi-trend mono">' + esc(g.device_ip || '') + '</span>' },
        { text: g.metric || g.family || '—', cls: 'mono' },
        { text: g.title || g.latest_content || '—', cls: 'strong' },
        { text: String(g.count || 0), cls: 'mono strong' },
        { text: String(g.resource_count || 0), cls: 'mono' },
        { html: '<span class="mono">' + esc(g.first_time || '—') + '</span><br/><span class="mono kpi-trend">' + esc(g.last_time || '—') + '</span>' },
        { html: g.open ? tag(g.status || '未恢复', 'warning') : tag(g.status || '已恢复', 'success') },
        { html: '<a class="link" data-alert-group="' + esc(g.key) + '" style="cursor:pointer">展开</a>' +
                (can('sync') ? ' · <a class="link" data-alert-dispose="' + esc(g.key) + '" style="cursor:pointer">处置</a>' : '') }
      ];
    });
    var tableCard = '<div class="card tight overview-module-card">' +
      cardHead('收敛后的告警分组', '共 ' + groupTotal + ' 组 · 第 ' + pageNo + '/' + totalPages + ' 页 · 每页 ' + pageSize + ' 条', '') +
      filter + '<div style="overflow-x:auto">' + (rows.length ? table(cols, rows) : emptyTable(cols, '所选条件下没有告警')) + '</div>' +
      pagerFooter('al', { total: groupTotal, page: pageNo, pages: totalPages, size: pageSize }, '组') + '</div>';
    var sev = data.group_by_severity || {};
    var statuses = data.group_by_status || {};
    var severityCard = '<div class="card tight">' + cardHead('告警级别与状态分布', '按聚合后的告警分组统计', '') + statList([
      { name: '紧急', value: String(sev.critical || 0) + ' 组' },
      { name: '严重', value: String(sev.major || 0) + ' 组' },
      { name: '警告', value: String(sev.warning || 0) + ' 组' },
      { name: '提示', value: String(sev.info || 0) + ' 组' }
    ].concat(Object.keys(statuses).map(function (k) {
      return { name: '状态 · ' + k, value: String(statuses[k]) + ' 组' };
    }))) + '</div>';
    var deviceCard = '<div class="card tight">' + cardHead('告警最多的设备', '按聚合后的组数与原始告警条数排序', '') +
      statList((data.by_device || []).map(function (d) {
        return { name: d.device || d.device_ip, value: String(d.groups || 0) + ' 组 / ' + String(d.alerts || 0) + ' 条' };
      })) + '</div>';
    var alertBody = alertTab === 'severity' ? severityCard : (alertTab === 'devices' ? deviceCard : tableCard);
    return head + alertTabs + kpiCards(kpis, true) + sourceNotice(data.source_info, data.source) + alertBody;
  }

  function bindAlerts(data) {
    STATE.alertGroups = data.groups || [];
    Array.prototype.forEach.call(document.querySelectorAll('[data-alert-tab]'), function (tab) {
      tab.addEventListener('click', function () {
        STATE.alerts.tab = tab.getAttribute('data-alert-tab');
        route();
      });
    });
    var submit = function (reset) {
      var a = STATE.alerts;
      a.hours = Number((document.getElementById('alHours') || {}).value || 168);
      a.severity = ((document.getElementById('alSeverity') || {}).value || '');
      a.status = ((document.getElementById('alStatus') || {}).value || '');
      a.keyword = ((document.getElementById('alKeyword') || {}).value || '').trim();
      a.device = ((document.getElementById('alDevice') || {}).value || '').trim();
      a.page_size = Number((document.getElementById('alSize') || {}).value || 10) || 10;
      if (reset) a.page = 1;
      var q = alertQuery();
      location.hash = '#/alerts' + (q ? '?' + q : '');
    };
    var q = document.getElementById('alQuery');
    if (q) q.addEventListener('click', function () { submit(true); });
    var pageSize = document.getElementById('alSize');
    if (pageSize) pageSize.addEventListener('change', function () { submit(true); });
    var prev = document.getElementById('alPrev');
    if (prev) prev.addEventListener('click', function () {
      if (STATE.alerts.page > 1) { STATE.alerts.page -= 1; var q = alertQuery(); location.hash = '#/alerts' + (q ? '?' + q : ''); }
    });
    var next = document.getElementById('alNext');
    if (next) next.addEventListener('click', function () {
      STATE.alerts.page += 1; var q = alertQuery(); location.hash = '#/alerts' + (q ? '?' + q : '');
    });
    var reset = document.getElementById('alReset');
    if (reset) reset.addEventListener('click', function () {
      STATE.alerts = { hours: 168, severity: '', status: '', keyword: '', device: '', limit: 500, page: 1, page_size: 10, tab: 'list' };
      location.hash = '#/alerts';
    });
    var refresh = document.getElementById('alRefresh');
    if (refresh) refresh.addEventListener('click', route);
    var exp = document.getElementById('alExport');
    if (exp) exp.addEventListener('click', function () {
      download(window.NetInspect.exportUrl({ kind: 'alerts', format: 'xlsx', hours: STATE.alerts.hours || 168 }));
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-alert-group]'), function (node) {
      node.addEventListener('click', function () { openAlertGroup(node.getAttribute('data-alert-group')); });
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-alert-dispose]'), function (node) {
      node.addEventListener('click', function () {
        var key = node.getAttribute('data-alert-dispose');
        var group = (STATE.alertGroups || []).filter(function (g) { return g.key === key; })[0];
        openAlertDisposition(group);
      });
    });
  }
  /* ---------- 页面：05 巡检报告中心 ---------- */
  function pageReports(data) {
    var archive = data.archive || { exports: [] };
    var ov = data.overview || {};
    var r = STATE.reports;
    var reportTab = ['archive', 'templates'].indexOf(r.tab) >= 0 ? r.tab : 'archive';
    r.tab = reportTab;
    var reportTabs = moduleTabs([
      { key: 'archive', label: '报告归档', icon: 'archive', count: archive.all_count || 0 },
      { key: 'templates', label: '模板与版式', icon: 'settings', count: (archive.templates || []).length }
    ], reportTab, 'report-tab', '<span class="kpi-trend">报告生成统一在设备健康页面完成</span>');
    var head =
      topbar('搜索报告名称 / 类型 / 导出人') +
      '<div class="page-head"><div class="page-title"><h1>巡检报告归档</h1>' +
      '<div class="page-sub"><span>' + esc(orgName()) + ' · 归档报告 ' + esc(archive.all_count || 0) + ' 份</span>' +
      '<span>报告由设备健康页面生成后自动归档</span></div></div></div>';

    var kindOptions = [{ value: 'all', label: '全部类型' }].concat(
      (archive.by_kind || []).map(function (k) { return { value: k.value, label: k.label + '（' + k.count + '）' }; }));
    var fmtOptions = [{ value: 'all', label: '全部格式' }, { value: 'xlsx', label: 'Excel（xlsx）' },
      { value: 'csv', label: 'CSV' }, { value: 'docx', label: 'Word（docx）' }, { value: 'pdf', label: 'PDF' }];
    var filter = '<div class="module-filter-block"><div class="form-row module-filter-row">' +
      field('关键字（报告名 / 导出人）', textBox('rpSearch', r.keyword, '例如 巡检明细 或 admin')) +
      field('关联设备 IP', textBox('rpDevice', r.device || '', '全部设备')) +
      field('报表类型', picker('rpKind', kindOptions, r.kind)) +
      field('导出格式', picker('rpFmt', fmtOptions, r.fmt)) +
      '</div><div class="btn-group" style="justify-content:flex-end">' +
      '<button class="btn btn-ghost sm" id="rpReset">重置</button>' +
      '<button class="btn btn-primary sm" id="rpQuery">查询</button></div></div>';

    var rows = (archive.exports || []).map(function (e) {
      return [
        { text: e.name, cls: 'strong' }, { text: e.kind_label || kindLabel(e.kind) },
        { text: String(e.format || '').toUpperCase(), cls: 'mono' },
        { text: e.rows + ' 行', cls: 'mono' }, { text: e.created_at, cls: 'mono' }, { text: e.operator },
        { html: '<a class="link" data-dl="' + e.id + '" data-fmt="' + esc(e.format) + '" style="cursor:pointer">下载</a>' +
            ' · <a class="link" data-del="' + e.id + '" style="cursor:pointer">删除</a>' }
      ];
    });
    var cols = [{ text: '报告名称', width: 280 }, { text: '报表类型', width: 140 },
      { text: '格式', width: 80 }, { text: '设备数', width: 90 }, { text: '导出时间', width: 170 },
      { text: '导出人', width: 90 }, { text: '操作', width: 110 }];

    var archiveCard = '<div class="card tight overview-module-card">' +
      cardHead('报告归档', '共 ' + esc(archive.total || 0) + ' 条 · 第 ' + esc(archive.page) + '/' + esc(archive.pages) + ' 页',
        '<span class="kpi-trend">归档保留已生成文件，可下载、删除与追溯</span>') +
      filter + '<div style="overflow-x:auto">' +
      (rows.length ? table(cols, rows) : emptyTable(cols, '还没有符合条件的归档报告，请先在对应设备健康页面生成报告')) +
      pagerFooter('rp', { total: archive.total, page: archive.page, pages: archive.pages, size: r.page_size }, '条') +
      '</div>';

    var templateList = (archive.templates || []).map(function (t) {
      return '<div class="report-template-row"><div><b>' + esc(t.name) + '</b><span>' +
        esc((t.sheets || []).join(' / ')) + (t.doc ? '（' + esc(t.doc) + '）' : '') + '</span></div>' +
        '<div class="btn-group"><a class="link" data-gen="' + esc(t.key) + '" style="cursor:pointer">导出 Excel</a></div></div>';
    }).join('');
    var templateCard = '<div class="card tight overview-module-card">' +
      cardHead('报告模板与输出格式', '模板定义报告结构；版式决定下载文件类型', '') +
      '<div class="report-template-list">' + (templateList || notice('报告模板接口暂未返回数据')) + '</div>' +
      '<div class="module-guidance"><div class="module-guidance-row"><span class="module-guidance-index">说明</span>' +
      '<p>Excel 用于数据复核和二次统计；正式 Word / PDF 报告统一从交换机、服务器、安全设备健康页面生成，生成后进入报告归档。</p></div></div></div>';

    var reportBody = reportTab === 'templates' ? templateCard : archiveCard;
    return head + reportTabs + kpiCards([
      { label: '归档报告', value: String(archive.all_count || 0), unit: '份', note: '本平台导出并归档', tone: 'muted' },
      { label: '巡检记录', value: String((ov.counts || {}).inspections || 0), unit: '条', note: '来自本平台采集结果', tone: 'success' },
      { label: '异常检查项', value: String((ov.abnormal || []).length), unit: '项', note: (ov.abnormal || []).length ? '需要处置' : '全部通过', tone: (ov.abnormal || []).length ? 'warning' : 'success' },
      { label: '数据源', value: sourceLabelOf(ov.source), unit: '', note: '页面 → FastAPI → 本地采集库', tone: 'muted' }
    ], true) + sourceNotice(ov.source_info, ov.source) + reportBody;
  }

  function reportsQuery() {
    var r = STATE.reports;
    var parts = [];
    if (r.tab && r.tab !== 'archive') parts.push('tab=' + encodeURIComponent(r.tab));
    if (r.keyword) parts.push('keyword=' + encodeURIComponent(r.keyword));
    if (r.device) parts.push('device=' + encodeURIComponent(r.device));
    if (r.category) parts.push('category=' + encodeURIComponent(r.category));
    if (r.kind && r.kind !== 'all') parts.push('kind=' + encodeURIComponent(r.kind));
    if (r.fmt && r.fmt !== 'all') parts.push('fmt=' + encodeURIComponent(r.fmt));
    if (Number(r.page) > 1) parts.push('page=' + r.page);
    if (Number(r.page_size) !== 20) parts.push('page_size=' + r.page_size);
    return parts.join('&');
  }

  function applyReportsQuery(query) {
    STATE.reports.tab = query.tab === 'templates' ? 'templates' : 'archive';
    STATE.reports.keyword = query.keyword || '';
    STATE.reports.device = query.device || '';
    STATE.reports.category = query.category || '';
    STATE.reports.kind = query.kind || 'all';
    STATE.reports.fmt = query.fmt || 'all';
    STATE.reports.page = Number(query.page || 1) || 1;
    STATE.reports.page_size = Number(query.page_size || 20) || 20;
  }

  function bindReports() {
    Array.prototype.forEach.call(document.querySelectorAll('[data-report-tab]'), function (tab) {
      tab.addEventListener('click', function () {
        STATE.reports.tab = tab.getAttribute('data-report-tab');
        refreshPageHash('reports', reportsQuery());
      });
    });
    var submit = function (resetPage) {
      var kw = document.getElementById('rpSearch');
      var kind = document.getElementById('rpKind');
      var fmt = document.getElementById('rpFmt');
      var size = document.getElementById('rpSize');
      STATE.reports.keyword = kw ? kw.value.trim() : '';
      STATE.reports.device = (document.getElementById('rpDevice') || {}).value || '';
      STATE.reports.device = STATE.reports.device.trim();
      STATE.reports.kind = kind ? kind.value : 'all';
      STATE.reports.fmt = fmt ? fmt.value : 'all';
      STATE.reports.page_size = Number(size ? size.value : 20) || 20;
      if (resetPage) STATE.reports.page = 1;
      var query = reportsQuery();
      var hash = '#/reports' + (query ? '?' + query : '');
      if (location.hash === hash) route(); else location.hash = hash;
    };
    var query = document.getElementById('rpQuery');
    if (query) query.addEventListener('click', function () { submit(true); });
    var box = document.getElementById('rpSearch');
    if (box) box.addEventListener('keydown', function (e) { if (e.key === 'Enter') submit(true); });
    var deviceInput = document.getElementById('rpDevice');
    if (deviceInput) deviceInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') submit(true); });
    ['rpKind', 'rpFmt', 'rpSize'].forEach(function (id) {
      var node = document.getElementById(id);
      if (node) node.addEventListener('change', function () { submit(true); });
    });
    var reset = document.getElementById('rpReset');
    if (reset) reset.addEventListener('click', function () {
      STATE.reports = { keyword: '', kind: 'all', fmt: 'all', page: 1, page_size: 20 };
      location.hash = '#/reports';
      if (key_href() === 'reports') route();
    });
    var prev = document.getElementById('rpPrev');
    if (prev) prev.addEventListener('click', function () {
      if (STATE.reports.page > 1) { STATE.reports.page -= 1; submit(false); }
    });
    var next = document.getElementById('rpNext');
    if (next) next.addEventListener('click', function () { STATE.reports.page += 1; submit(false); });
    Array.prototype.forEach.call(document.querySelectorAll('[data-dl]'), function (link) {
      link.addEventListener('click', function () {
        download(window.NetInspect.reExportUrl(link.getAttribute('data-dl'),
          link.getAttribute('data-fmt') || 'xlsx'));
      });
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-del]'), function (link) {
      link.addEventListener('click', function () {
        var id = link.getAttribute('data-del');
        window.NetInspect.removeArchive(id).then(route).catch(function (err) { showToast('删除失败：' + err.message); });
      });
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-gen]'), function (link) {
      link.addEventListener('click', function () {
        download(window.NetInspect.exportUrl({ kind: link.getAttribute('data-gen'), format: 'xlsx', hours: 24 * 30 }));
        setTimeout(route, 1500);
      });
    });
  }

  function kindLabel(kind) {
    return { overview: '巡检总览', inspection: '巡检明细', devices: '设备台账',
      server: '服务器健康', switch: '交换机健康', security: '安全设备健康', alerts: '告警处置', backup: '配置备份' }[kind] || kind;
  }


  /* ---------- 页面：12 配置备份中心 ---------- */
  function pageBackup(data) {
    var b = STATE.backup;
    var validTabs = ['files', 'coverage', 'rules'];
    var tab = validTabs.indexOf(b.tab) >= 0 ? b.tab : 'files';
    b.tab = tab;
    var coverage = data.coverage || [];
    var head =
      topbar('搜索备份文件 / 设备 IP') +
      '<div class="page-head"><div class="page-title"><h1>配置备份中心</h1>' +
      '<div class="page-sub"><span>备份文件 ' + esc(data.file_count || 0) + ' 份 · 已覆盖 ' + esc(data.devices_covered || 0) +
      '/' + esc(data.devices_total || 0) + ' 台设备 · 最近 ' + esc(data.newest || '—') + '</span>' +
      '<span>匹配 ' + esc(data.total || 0) + ' 条 · 数据源 ' + esc(sourceLabelOf(data.source)) + '</span></div></div>' +
      '<div class="cta-row">' +
      '<button class="btn btn-ghost" id="bkPackage">' + icon('download', 14) + '导出实时配置包</button>' +
      '<button class="btn btn-ghost" id="bkExport">导出备份清单</button>' +
      '<button class="btn btn-primary" id="bkSync">' + icon('refresh', 14) + '刷新</button></div></div>';

    var kpis = [
      { label: '备份文件总数', value: String(data.file_count || 0), unit: '份',
        note: (data.source === 'local' || data.source === 'mirror') ? '历史归档；实时下载不落盘' : '备份目录扫描结果', tone: 'default' },
      { label: '设备覆盖率', value: (data.devices_total ? Math.round(100 * (data.devices_covered || 0) / data.devices_total) : 0) + '%', unit: '',
        note: '已备份 ' + (data.devices_covered || 0) + ' / ' + (data.devices_total || 0) + ' 台',
        tone: (data.devices_covered || 0) >= (data.devices_total || 0) ? 'success' : 'warning' },
      { label: '备份总容量', value: data.total_size_text || '—', unit: '', note: '配置文本快照合计', tone: 'default' },
      { label: '最近一次备份', value: data.newest || '—', unit: '', note: '按备份目录最新修改时间', tone: 'default' }
    ];

    var filter = '<div class="module-filter-block"><div class="form-row module-filter-row">' +
      field('关键字（文件名 / 设备 IP）', textBox('bkSearch', b.keyword, '例如 10.10.0.1 或 backup_10.10')) +
      '</div><div class="btn-group" style="justify-content:flex-end">' +
      '<button class="btn btn-ghost sm" id="bkReset">重置</button>' +
      '<button class="btn btn-primary sm" id="bkQuery">查询</button></div></div>';

    var cols = [{ text: '备份文件', width: 300 }, { text: '设备 IP', width: 150 },
      { text: '大小', width: 110 }, { text: '备份时间', width: 180 }, { text: '操作', width: 110 }];
    var files = '<div class="card tight overview-module-card">' +
      cardHead('备份文件清单', '共 ' + esc(data.total || 0) + ' 条 · 第 ' + esc(data.page) + '/' + esc(data.pages) + ' 页',
        '<span class="kpi-trend">每台设备独立文件 · 交换机 .cfg / 服务器按设备名目录</span>') +
      filter + '<div style="overflow-x:auto">' +
      ((data.files || []).length ? table(cols, data.files.map(function (f) {
        return [
          { text: f.name, cls: 'strong' }, { text: f.device_ip, cls: 'mono' }, { text: f.size_text, cls: 'mono' },
          { text: f.time_text, cls: 'mono' },
          { html: '<a class="link" data-pkg="' + esc(f.device_ip) + '" style="cursor:pointer">下载配置</a>' }
        ];
      })) : emptyTable(cols, '当前没有历史备份文件；点右上角「导出实时配置包」，交换机会执行 dis cu，服务器会读取备份目录，统一打包下载')) +
      pagerFooter('bk', { total: data.total, page: data.page, pages: data.pages, size: b.page_size }, '条') +
      '</div>';

    var coverView = clientPage(coverage, b, 'coverage_page', 'coverage_size', [10, 20, 50], 10);
    var coverageCard = '<div class="card tight overview-module-card">' +
      cardHead('备份覆盖情况', '未备份设备 ' + coverage.length + ' 台 · 点击设备可进入台账查看',
        '<span class="chip ' + (coverage.length ? 'warning' : 'success') + '">覆盖率 ' +
        (data.devices_total ? Math.round(100 * (data.devices_covered || 0) / data.devices_total) : 0) + '%</span>') +
      (coverage.length ? '<div class="stat-list module-device-list">' + coverView.rows.map(function (d) {
        return '<div class="stat-item" data-cov="' + esc(d.ip) + '" style="cursor:pointer"><span class="n">' + esc(d.name) + '</span><span class="v">' + esc(d.ip) + '</span></div>';
      }).join('') + '</div>' : notice('所有已登记设备都有备份')) +
      pagerFooter('bkCover', coverView, '台') + '</div>';

    var advice = [
      '「导出实时配置包」会实时 SSH 登录：交换机执行 dis cu，每台生成一个以设备名命名的 .cfg；服务器进入采集设置中的备份目录，按设备名建立文件夹并保留原始备份文件。所有文件统一合成一个 ZIP 直接下载。',
      'ZIP 在内存中生成，不会把汇总配置写成一个 txt，也不会在服务器保存打包文件。列表仅用于查询历史归档记录。',
      '建议按设备类型设置备份周期：核心交换机每周、接入交换机每周、防火墙策略每月。',
      '新设备上线后确认已纳入备份范围，避免出现「有台账没备份」的空档。',
      '配置变更前后各留一份快照，回滚时有据可依。'
    ];
    var rulesCard = '<div class="card tight overview-module-card">' +
      cardHead('备份策略建议', '采集只读，不改设备配置；以下为运维建议', '') +
      '<div class="module-guidance">' + advice.map(function (t, i) {
        return '<div class="module-guidance-row"><span class="module-guidance-index">' + String(i + 1).padStart(2, '0') + '</span><p>' + esc(t) + '</p></div>';
      }).join('') + '</div></div>';

    var sourceCard = '<div class="card tight overview-module-card">' +
      cardHead('数据来源', '备份清单与设备台账的取数路径', '') + statList([
        { name: '备份清单', value: (data.source === 'local' || data.source === 'mirror')
            ? '交换机 dis cu + 服务器备份目录（SSH/SFTP）' : '本平台备份目录' },
        { name: '设备台账', value: (data.source === 'local' || data.source === 'mirror')
            ? '本平台台账（设备清单）' : '本平台台账' },
        { name: '当前数据源', value: sourceLabelOf(data.source) },
        { name: '刷新方式', value: '按页查询，刷新后保持当前模块与页码' }
      ]) + '</div>';

    var tabs = moduleTabs([
      { key: 'files', label: '备份文件', icon: 'archive', count: data.total || 0 },
      { key: 'coverage', label: '覆盖情况', icon: 'server', count: coverage.length },
      { key: 'rules', label: '备份策略', icon: 'check', count: advice.length }
    ], tab, 'backup-tab', '<span>按标签页切换备份内容</span>');

    var body = tab === 'coverage' ? coverageCard : tab === 'rules' ? rulesCard : files;
    return head + sourceNotice(data.source_info, data.source) + kpiCards(kpis, true) + tabs + body;
  }

  function backupQuery() {
    var b = STATE.backup;
    var parts = [];
    if (b.tab && b.tab !== 'files') parts.push('tab=' + encodeURIComponent(b.tab));
    if (b.keyword) parts.push('keyword=' + encodeURIComponent(b.keyword));
    if (Number(b.page) > 1) parts.push('page=' + b.page);
    if (Number(b.page_size) !== 20) parts.push('page_size=' + b.page_size);
    if (Number(b.coverage_page) > 1) parts.push('coverage_page=' + b.coverage_page);
    if (Number(b.coverage_size) !== 10) parts.push('coverage_size=' + b.coverage_size);
    return parts.join('&');
  }

  function applyBackupQuery(query) {
    var b = STATE.backup;
    b.tab = ['files', 'coverage', 'rules'].indexOf(query.tab) >= 0 ? query.tab : 'files';
    b.keyword = query.keyword || '';
    b.page = Number(query.page || 1) || 1;
    b.page_size = [10, 20, 50].indexOf(Number(query.page_size)) >= 0 ? Number(query.page_size) : 20;
    b.coverage_page = Number(query.coverage_page || 1) || 1;
    b.coverage_size = [10, 20, 50].indexOf(Number(query.coverage_size)) >= 0 ? Number(query.coverage_size) : 10;
  }

  function bindBackup() {
    var submit = function (resetPage) {
      var kw = document.getElementById('bkSearch');
      var size = document.getElementById('bkSize');
      STATE.backup.keyword = kw ? kw.value.trim() : '';
      STATE.backup.page_size = Number(size ? size.value : 20) || 20;
      if (resetPage) STATE.backup.page = 1;
      refreshPageHash('backup', backupQuery());
    };
    var query = document.getElementById('bkQuery');
    if (query) query.addEventListener('click', function () { submit(true); });
    var box = document.getElementById('bkSearch');
    if (box) box.addEventListener('keydown', function (e) { if (e.key === 'Enter') submit(true); });
    var size = document.getElementById('bkSize');
    if (size) size.addEventListener('change', function () { submit(true); });
    var reset = document.getElementById('bkReset');
    if (reset) reset.addEventListener('click', function () {
      STATE.backup = { keyword: '', page: 1, page_size: 20, tab: 'files', coverage_page: 1, coverage_size: 10 };
      location.hash = '#/backup';
      if (key_href() === 'backup') route();
    });
    var prev = document.getElementById('bkPrev');
    if (prev) prev.addEventListener('click', function () {
      if (STATE.backup.page > 1) { STATE.backup.page -= 1; submit(false); }
    });
    var next = document.getElementById('bkNext');
    if (next) next.addEventListener('click', function () { STATE.backup.page += 1; submit(false); });
    bindModuleTabs('backup-tab', function (tabKey) {
      STATE.backup.tab = tabKey;
      refreshPageHash('backup', backupQuery());
    });
    bindClientPager('bkCover', STATE.backup, 'coverage_page', 'coverage_size', function () {
      refreshPageHash('backup', backupQuery());
    });
    var ex = document.getElementById('bkExport');
    if (ex) ex.addEventListener('click', function () { download(window.NetInspect.exportUrl({ kind: 'backup', format: 'xlsx' })); });
    var sync = document.getElementById('bkSync');
    if (sync) sync.addEventListener('click', route);
    var pack = document.getElementById('bkPackage');
    if (pack) pack.addEventListener('click', function () {
      download(window.NetInspect.packageBackupsUrl(), { label: '配置备份包', ext: 'zip', progress: true });
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-pkg]'), function (node) {
      node.addEventListener('click', function () {
        download(window.NetInspect.packageBackupsUrl(node.getAttribute('data-pkg')),
          { label: '设备配置', ext: 'zip', progress: true });
      });
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-cov]'), function (node) {
      node.addEventListener('click', function () {
        STATE.devices.keyword = node.getAttribute('data-cov');
        STATE.devices.page = 1;
        location.hash = '#/devices?keyword=' + encodeURIComponent(node.getAttribute('data-cov'));
      });
    });
  }


  /* ---------- 页面：13 报告与采集模板（模板目录为原型静态内容） ---------- */
  

  


  /* ---------- 页面：16 用户与权限管理（本平台自己的账号体系） ---------- */
  /* ---------- 页面：用户与权限（真实账号管理 + 登录审计） ---------- */
  function pageUsers(data) {
    var accounts = (data.accounts || {}).users || [];
    var roles = (data.accounts || {}).roles || [];
    var audit = data.audit || { rows: [], by_user: [], by_action: {}, action_labels: {} };
    var events = {
      total: audit.total || 0,
      failed: (audit.rows || []).filter(function (row) { return row.action === 'login_failed'; }).length,
      action_labels: audit.action_labels || {}
    };
    var perms = STATE.perms || {};
    var me = STATE.user || {};
    var rawUsersTab = STATE.usersTab;
    if (rawUsersTab === 'login' || rawUsersTab === 'operations') rawUsersTab = 'audit';
    var usersTab = ['accounts', 'audit', 'permissions', 'security'].indexOf(rawUsersTab) >= 0
      ? rawUsersTab : 'accounts';
    STATE.usersTab = usersTab;
    var usersTabs = moduleTabs([
      { key: 'accounts', label: '账号管理', icon: 'users', count: accounts.length },
      { key: 'audit', label: '审计日志', icon: 'file', count: audit.total || 0 },
      { key: 'permissions', label: '权限说明', icon: 'lock' },
      { key: 'security', label: '账号安全', icon: 'shield' }
    ], usersTab, 'users-tab', '<span class="kpi-trend">账号、权限与审计统一管理</span>');

    var head =
      topbar('搜索账号 / 姓名 / 角色 / 登录来源') +
      '<div class="page-head"><div class="page-title"><h1>用户与权限管理</h1>' +
      '<div class="page-sub"><span>平台账号 ' + (accounts.length || 0) + ' 个 · 审计日志 ' + (audit.total || 0) +
      ' 条</span>' +
      '<span>当前账号：' + esc(me.display_name || me.username || '') + '（' + esc(perms.role_label || '') + '）</span></div></div>' +
      '<div class="cta-row">' +
      (usersTab === 'accounts' && perms.users ? '<button class="btn btn-primary" id="usNew">新建账号</button>' : '') +
      (usersTab === 'audit' ? '<button class="btn btn-ghost" id="usEvents">' +
        (perms.users ? '导出审计日志' : '导出我的审计记录') + '</button>' : '') +
      '</div></div>';

    var actionOptions = [{ value: 'all', label: '全部动作' }].concat(
      Object.keys(events.action_labels || {}).map(function (key) {
        return { value: key, label: events.action_labels[key] };
      }));
    var periodOptions = [{ value: '24', label: '近 1 天' }, { value: '168', label: '近 7 天' },
      { value: '720', label: '近 30 天' }, { value: '2160', label: '近 90 天' }];

    var kpis = [
      { label: '平台账号', value: perms.users ? String(accounts.length) : '—', unit: '个',
        note: perms.users ? ('启用 ' + accounts.filter(function (a) { return a.enabled; }).length + ' 个') : '非管理员不展示账号清单',
        tone: 'default' },
      { label: '超级管理员', value: perms.users ? String(accounts.filter(function (a) { return a.is_admin && a.enabled; }).length) : '—', unit: '个', note: '至少保留一个', tone: 'warning' },
      { label: '审计日志', value: String(events.total || 0), unit: '条', note: '登录 / 账号 / 设备 / 采集 / 远程操作', tone: 'default' },
      { label: '失败登录', value: String(events.failed || 0), unit: '次', note: '口令错误或账号停用', tone: (events.failed ? 'warning' : 'success') }
    ];

    var tableHtml = '';
    if (perms.users) {
      var rows = accounts.map(function (a) {
        return [
          { text: a.username, cls: 'strong' },
          { text: a.display_name || '—' },
          { html: tag(a.role_label, a.is_admin ? 'danger' : a.role === 'operator' ? 'brand' : 'neutral') },
          { html: a.enabled ? tag('启用', 'success') : tag('已停用', 'neutral') },
          { text: a.last_login_at || '尚未登录', cls: 'mono' },
          { text: a.last_login_ip || '—', cls: 'mono' },
          { text: (a.sessions || 0) + ' 个', cls: 'mono' },
          { html:
              '<a class="link" data-edit="' + a.id + '" style="cursor:pointer">编辑</a>' +
              ' · <a class="link" data-pass="' + a.id + '" style="cursor:pointer">重置口令</a>' +
              ' · <a class="link" data-toggle="' + a.id + '" data-enabled="' + (a.enabled ? '1' : '0') + '" style="cursor:pointer">' + (a.enabled ? '停用' : '启用') + '</a>' +
              (a.username === me.username ? '' : ' · <a class="danger-link" data-del="' + a.id + '" style="cursor:pointer">删除</a>') }
        ];
      });
      var cols = [{ text: '登录账号', width: 150 }, { text: '姓名', width: 110 }, { text: '角色', width: 120 },
        { text: '状态', width: 90 }, { text: '最近登录', width: 160 }, { text: '来源 IP', width: 130 },
        { text: '在线会话', width: 90 }, { text: '操作', width: 240 }];
      tableHtml = '<div class="card tight">' + cardHead('平台账号', '账号是本平台的登录凭据，按角色控制写操作', '') +
        '<div style="overflow-x:auto">' + table(rows.length ? cols : cols, rows) + '</div></div>';
    } else {
      tableHtml = '<div class="card tight">' + cardHead('我的账号', '', '') + statList([
        { name: '登录账号', value: me.username || '—' },
        { name: '姓名', value: me.display_name || '—' },
        { name: '角色', value: perms.role_label || '—' },
        { name: '最近登录', value: (STATE.overview.last_login || {}).at || '—' },
        { name: '权限说明', value: '只读 + 导出；台账写入、远程登录与系统设置需要更高角色' }
      ]) + '</div>';
    }

    var auditFilter = '<div class="module-filter-block"><div class="form-row module-filter-row">' +
      field('操作人', textBox('usSearch', (STATE.audit || {}).username || '', '账号名，如 admin')) +
      field('动作', picker('usAction', actionOptions, (STATE.audit || {}).action || 'all')) +
      field('时间区间', picker('usHours', periodOptions, String((STATE.audit || {}).hours || 168))) +
      field('关键字（对象名 / 详情）', textBox('usKeyword', (STATE.audit || {}).keyword || '', '例如 HN-CORE-SW01')) +
      '</div><div class="btn-group" style="justify-content:flex-end">' +
      '<button class="btn btn-ghost sm" id="usReset">重置</button>' +
      '<button class="btn btn-primary sm" id="usQuery">查询</button></div></div>';

    var opView = clientPage(audit.rows || [], STATE.audit, 'op_page', 'op_size', [10, 20, 50], 10);
    var npRows = opView.rows.map(function (row) {
      return [
        { text: row.time, cls: 'mono' },
        { text: row.username, cls: 'strong' },
        { html: tag(row.action_label, row.action === 'delete' ? 'danger' : row.action === 'create' ? 'success' : 'neutral') },
        { text: row.object_type },
        { text: row.object_name, cls: 'strong' },
        { text: (row.detail || '').slice(0, 60) }
      ];
    });
    var npCols = [{ text: '时间', width: 150 }, { text: '操作人', width: 100 }, { text: '动作', width: 90 },
      { text: '对象类型', width: 110 }, { text: '对象', width: 200 }, { text: '详情' }];
    var npBody;
    if (audit.pending) {
      npBody = notice('正在读取操作审计…');
    } else if (audit.available === false) {
      npBody = notice('审计日志不可用：' + esc(audit.error || '未知原因') +
                      '（该接口只对管理员令牌开放）', 'danger');
    } else {
      npBody = '<div style="overflow-x:auto">' + (npRows.length ? table(npCols, npRows)
        : emptyTable(npCols, '所选区间没有审计记录')) + '</div>' + pagerFooter('usOps', opView, '条');
    }
    var npCard = '<div class="card tight overview-module-card" id="npAuditCard">' +
      cardHead('审计日志', '登录、账号、台账、采集和远程操作统一留痕（只读）', '') + auditFilter + npBody + '</div>';

    var roleCard = '<div class="card">' + cardHead('角色与权限口径', '', '') + statList([
      { name: '超级管理员', value: '全部功能 + 账号管理 + 系统设置 + 远程控制台全权限' },
      { name: '运维工程师', value: '台账写入 / 导入 / 触发采集 / 受策略约束的 SSH 与 SFTP' },
      { name: '只读用户', value: '查看与导出报表' }
    ]) + '</div>';
    var securityCard = '<div class="card">' + cardHead('账号安全', '', '') + statList([
      { name: '口令存储', value: 'PBKDF2-SHA256（20 万次迭代 + 随机盐）' },
      { name: '会话令牌', value: '随机 32 字节，库里只存 SHA-256 摘要' },
      { name: '会话有效期', value: '12 小时；勾选「记住我」30 天' },
      { name: '登录留痕', value: '登录 / 退出 / 失败 / 改口令全部入库' }
    ]) + '</div>';

    var usersBody;
    if (usersTab === 'audit') usersBody = npCard;
    else if (usersTab === 'permissions') usersBody = roleCard;
    else if (usersTab === 'security') usersBody = securityCard;
    else usersBody = tableHtml;
    return head + usersTabs + kpiCards(kpis, true) + usersBody;
  }

  function openUserModal(user) {
    var editing = !!user;
    var roles = ((STATE.usersData || {}).roles) || [];
    var inner =
      '<div class="modal" style="width:600px">' +
      '<div class="card-head" style="margin-bottom:14px"><div class="t">' +
      '<div class="title" style="font-size:18px">' + (editing ? '编辑账号' : '新建账号') + '</div>' +
      '<div class="sub">账号用于登录本平台；角色决定能不能改台账、远程登录、改设置</div></div>' +
      '<button class="icon-btn" id="umClose" style="width:32px;height:32px">' + icon('close', 16) + '</button></div>' +
      '<div class="form-row">' +
      field('登录账号', editing ? lockedInput(user.username) : plainBox('umUser', '', 'text')) +
      field('姓名', plainBox('umName', user ? user.display_name : '')) +
      '</div>' +
      '<div class="form-row">' +
      field('角色', picker('umRole', roles.map(function (r) { return { value: r.value, label: r.label }; }),
        user ? user.role : 'viewer')) +
      (editing ? '<div class="field"><label>状态</label>' + picker('umEnabled', [
        { value: '1', label: '启用' }, { value: '0', label: '停用' }],
        user.enabled ? '1' : '0') + '</div>'
      : '<div class="field"><label>初始口令</label>' + plainBox('umPass', '', 'password') + '</div>') +
      '</div>' +
      field('备注', plainBox('umNote', user ? user.note : '')) +
      '<div id="umResult"></div>' +
      '<div class="footer-bar"><span class="kpi-trend">' + (editing ? '口令用「重置口令」单独处理' : '口令至少 8 位，含两类字符') + '</span>' +
      '<div class="btn-group"><button class="btn btn-ghost" id="umCancel">取消</button>' +
      '<button class="btn btn-primary" id="umSave">' + (editing ? '保存修改' : '创建账号') + '</button></div></div></div>';
    showOverlay(inner, false);
    var save = document.getElementById('umSave');
    if (save) save.addEventListener('click', function () {
      var payload = {
        display_name: (document.getElementById('umName') || {}).value || '',
        role: (document.getElementById('umRole') || {}).value || 'viewer',
        note: (document.getElementById('umNote') || {}).value || ''
      };
      var promise;
      if (editing) {
        payload.enabled = (document.getElementById('umEnabled') || {}).value === '1';
        promise = window.NetInspect.updateUser(user.id, payload);
      } else {
        payload.username = (document.getElementById('umUser') || {}).value || '';
        payload.password = (document.getElementById('umPass') || {}).value || '';
        promise = window.NetInspect.createUser(payload);
      }
      save.textContent = '保存中…';
      promise.then(function () {
        showToast(editing ? '账号已更新' : '账号已创建');
        closeOverlay();
        route();
      }).catch(function (err) {
        save.textContent = editing ? '保存修改' : '创建账号';
        document.getElementById('umResult').innerHTML = notice(err.message, 'danger');
      });
    });
  }

  function openResetPasswordModal(user) {
    var inner =
      '<div class="dialog" style="width:520px">' +
      '<div class="card-head"><div class="t"><div class="title">重置账号口令</div>' +
      '<div class="sub">' + esc(user.username) + ' · 重置后该账号的所有会话立即失效</div></div>' +
      '<button class="icon-btn" id="rpClose2" style="width:32px;height:32px">' + icon('close', 16) + '</button></div>' +
      field('新口令（≥8 位，含两类字符）', plainBox('rsPass', '', 'password')) +
      '<fieldset>' + field('确认新口令', plainBox('rsPass2', '', 'password')) + '</fieldset>' +
      '<div id="rsResult"></div>' +
      '<div class="footer-bar"><span class="kpi-trend">改完请把新口令当面告知使用人</span>' +
      '<div class="btn-group"><button class="btn btn-ghost" id="rsCancel">取消</button>' +
      '<button class="btn btn-primary" id="rsSave">重置</button></div></div></div>';
    showOverlay(inner, false);
    var save = document.getElementById('rsSave');
    if (save) save.addEventListener('click', function () {
      var one = (document.getElementById('rsPass') || {}).value || '';
      var two = (document.getElementById('rsPass2') || {}).value || '';
      if (one !== two) { showToast('两次输入不一致'); return; }
      window.NetInspect.resetUserPassword(user.id, one).then(function () {
        showToast('口令已重置');
        closeOverlay();
        route();
      }).catch(function (err) {
        document.getElementById('rsResult').innerHTML = notice(err.message, 'danger');
      });
    });
  }

  function bindUsers(data) {
    STATE.usersData = data.accounts || {};
    Array.prototype.forEach.call(document.querySelectorAll('[data-users-tab]'), function (tab) {
      tab.addEventListener('click', function () {
        STATE.usersTab = tab.getAttribute('data-users-tab');
        route();
      });
    });
    STATE.audit = STATE.audit || { hours: 168 };
    bindClientPager('usOps', STATE.audit, 'op_page', 'op_size', route);
    var submitAudit = function () {
      var user = document.getElementById('usSearch');
      var action = document.getElementById('usAction');
      var hours = document.getElementById('usHours');
      var keyword = document.getElementById('usKeyword');
      STATE.audit.username = user ? user.value.trim() : '';
      STATE.audit.action = action ? action.value : 'all';
      STATE.audit.hours = Number(hours ? hours.value : 168) || 168;
      STATE.audit.keyword = keyword ? keyword.value.trim() : '';
      var parts = [];
      if (STATE.audit.username) parts.push('username=' + encodeURIComponent(STATE.audit.username));
      if (STATE.audit.action && STATE.audit.action !== 'all') parts.push('action=' + encodeURIComponent(STATE.audit.action));
      if (STATE.audit.keyword) parts.push('q=' + encodeURIComponent(STATE.audit.keyword));
      if (STATE.audit.hours !== 168) parts.push('hours=' + STATE.audit.hours);
      var hash = '#/users' + (parts.length ? '?' + parts.join('&') : '');
      if (location.hash === hash) route(); else location.hash = hash;
    };
    var query = document.getElementById('usQuery');
    if (query) query.addEventListener('click', submitAudit);
    Array.prototype.forEach.call(['usSearch', 'usKeyword'], function (id) {
      var node = document.getElementById(id);
      if (node) node.addEventListener('keydown', function (e) { if (e.key === 'Enter') submitAudit(); });
    });
    Array.prototype.forEach.call(['usAction', 'usHours'], function (id) {
      var node = document.getElementById(id);
      if (node) node.addEventListener('change', submitAudit);
    });
    var resetFilter = document.getElementById('usReset');
    if (resetFilter) resetFilter.addEventListener('click', function () {
      STATE.audit = { username: '', action: 'all', keyword: '', hours: 168, op_page: 1, op_size: 10 };
      location.hash = '#/users';
      if (key_href() === 'users') route();
    });
    var newBtn = document.getElementById('usNew');
    if (newBtn) newBtn.addEventListener('click', function () { openUserModal(null); });
    var exp = document.getElementById('usEvents');
    if (exp) exp.addEventListener('click', function () {
      download(window.NetInspect.exportUrl({ kind: 'audit', format: 'xlsx', hours: 720 }));
    });
    var accounts = ((data.accounts || {}).users) || [];
    var find = function (id) { return accounts.filter(function (a) { return String(a.id) === String(id); })[0]; };
    Array.prototype.forEach.call(document.querySelectorAll('[data-edit]'), function (node) {
      node.addEventListener('click', function () { openUserModal(find(node.getAttribute('data-edit'))); });
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-pass]'), function (node) {
      node.addEventListener('click', function () { openResetPasswordModal(find(node.getAttribute('data-pass'))); });
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-toggle]'), function (node) {
      node.addEventListener('click', function () {
        var id = node.getAttribute('data-toggle');
        var target = find(id);
        var enable = node.getAttribute('data-enabled') !== '1';
        window.NetInspect.updateUser(id, { enabled: enable }).then(function () {
          showToast(enable ? '账号已启用' : '账号已停用');
          route();
        }).catch(function (err) { showToast('操作失败：' + err.message); });
      });
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-del]'), function (node) {
      node.addEventListener('click', function () {
        var id = node.getAttribute('data-del');
        var target = find(id);
        window.NetInspect.deleteUser(id).then(function () {
          showToast('账号已删除');
          route();
        }).catch(function (err) { showToast('删除失败：' + err.message); });
      });
    });
  }

  

  function applyAuditQuery(query) {
    STATE.audit.username = query.username || '';
    STATE.audit.action = query.action || 'all';
    STATE.audit.keyword = query.q || '';
    STATE.audit.hours = Number(query.hours || 168) || 168;
  }

  /* ---------- 页面：系统设置（平台标识 + 本地采集设置） ---------- */
  function pageSettings(data) {
    var st = data.status || {};
    var canEdit = can('settings');
    var settings = st.settings || {};
    var counts = st.counts || {};
    var collect = data.collect || {};
    var diag = data.diagnostics || {};
    var backups = data.backups || {};
    var lastCollect = (collect.last_run || {}).finished_at || collect.last_collect_at || '尚未采集';
    var settingsTab = ['platform', 'datasource', 'diagnostics', 'backup'].indexOf(STATE.settingsTab) >= 0
      ? STATE.settingsTab : 'platform';
    var settingsTabs = moduleTabs([
      { key: 'platform', label: '平台标识', icon: 'settings' },
      { key: 'datasource', label: '数据源', icon: 'network' },
      { key: 'diagnostics', label: '运行诊断', icon: 'gauge' },
      { key: 'backup', label: '平台备份', icon: 'archive' },
    ], settingsTab, 'settings-tab', '<span class="kpi-trend">配置、运行状态与备份独立维护</span>');

    var head =
      topbar('搜索设置项') +
      '<div class="page-head"><div class="page-title"><h1>系统设置</h1>' +
      '<div class="page-sub"><span>平台标识 · 采集方式 · 运行诊断与备份</span>' + sourceBadge() + '</div></div>' +
      '<div class="cta-row">' +
      (settingsTab === 'diagnostics' ? '<button class="btn btn-ghost" id="stRefresh">' + icon('refresh', 14) + '刷新状态</button>' :
        (settingsTab === 'backup' ? '<button class="btn btn-ghost" id="stRefresh">' + icon('refresh', 14) + '刷新备份列表</button>' :
          ((settingsTab === 'platform' || settingsTab === 'datasource') ?
            (canEdit ? '<button class="btn btn-primary" id="stSave">保存设置</button>'
                     : '<span class="chip warning">当前角色只读</span>') :
            '<a class="btn btn-ghost" href="#/pending">前往设备采集</a>'))) + '</div></div>';

    // /api/system/meta 没取到时就退回内置区间，避免下拉框显示「暂无可选项」
    var periodOptions = ((STATE.meta || {}).periods || []).map(function (p) {
      return { value: p.key, label: p.label };
    });
    if (!periodOptions.length) {
      periodOptions = [{ value: '1', label: '近 1 天' }, { value: '7', label: '近 7 天' },
                       { value: '30', label: '近 30 天' }, { value: '90', label: '近 90 天' }];
    }

    var basic = '<div class="card">' +
      cardHead('平台标识', '修改后立即同步到页眉、报表封面、报告封面与导出文件名', '') +
      '<div class="form-row">' +
      field('平台名称', plainBox('stSiteName', settings.site_name || '')) +
      field('组织单位（页眉显示）', plainBox('stOrgName', settings.org_name || '')) +
      field('默认统计区间', picker('stPeriod', periodOptions, settings.period_days || '7')) +
      '</div>' +
      '<div class="summary-bar" style="margin-top:14px">' +
      '<div class="info"><span class="n" id="orgPreview">' +
      esc(settings.org_name || '未设置') + '</span>' +
      '<span class="m">页眉预览 · 保存后全平台生效</span></div></div>' +
      '</div>';

    // 纯本地采集：没有数据源切换，也没有外部平台连接配置
    var conn = '<div class="card">' +
      cardHead('数据源', '本平台自带采集：自己 SSH 采华为交换机与 Linux / Windows 服务器，不依赖任何外部平台',
               tag('纯本地', 'brand')) +
      '<div class="form-row">' +
      field('采集方式', input('本平台自带采集（SSH 只读命令）', true)) +
      field('缓存 TTL（秒）', plainBox('stCacheTtl', settings.cache_ttl || '20')) +
      '</div>' +
      '<div style="font-size:11px;color:var(--text-3)">巡检、监控、告警、配置备份与命令回显都写在本机 SQLite；' +
      '新增设备后到「资产与采集 → 设备采集」配好 SSH 凭据并采一次即可。</div>' +
      (canEdit ? '<div class="btn-group" style="justify-content:flex-end;margin-top:12px">' +
        '<button class="btn btn-primary sm" id="stSave2">保存设置</button></div>' : '') +
      '</div>';

    var statusCard = '<div class="card">' + cardHead('数据与采集体检', '', '') + statList([
      { name: '数据源', value: '本平台自带采集（本地库）' },
      { name: '采集方式', value: 'SSH 只读（华为 VRP / Linux / Windows）' },
      { name: '本地台账 / 巡检记录', value: (counts.devices || 0) + ' / ' + (counts.inspections || 0) },
      { name: '告警 / 备份', value: (counts.alerts || 0) + ' / ' + (counts.backups || 0) },
      { name: '最近采集', value: lastCollect }
    ]) + '</div>';

    var tls = diag.tls || {};
    var scheduler = diag.scheduler || {};
    var backupRows = backups.backups || [];
    var diagCard = '<div class="card tight">' + cardHead('运行体检', '磁盘、数据库、证书、定时采集与备份状态', '') +
      statList([
        { name: '数据目录', value: fmtBytes(diag.data_size_bytes || 0) },
        { name: 'SQLite', value: fmtBytes(diag.database_size_bytes || 0) },
        { name: '磁盘剩余', value: fmtBytes(diag.disk_free_bytes || 0) + ' / ' + String(diag.disk_free_percent || 0) + '%' },
        { name: 'TLS 证书剩余', value: tls.error ? tls.error : (String(tls.days_left || 0) + ' 天') },
        { name: '定时采集', value: scheduler.running ? '采集执行中' : ('上次完成 ' + (scheduler.last_finished || '—')) },
        { name: '自动备份', value: String(backups.auto_backup_hours || diag.auto_backup_hours || '24') + ' 小时 / 保留 ' + String(backups.backup_keep || diag.backup_keep || 7) + ' 份' }
      ]) + '</div>';

    var backupList = backupRows.length ? backupRows.slice(0, 5).map(function (b) {
      return '<div class="stat-item"><span style="min-width:0;overflow:hidden;text-overflow:ellipsis">' + esc(b.name) + '</span>' +
        '<span class="mono kpi-trend">' + fmtBytes(b.size || 0) + '</span>' +
        '<a class="link" data-backup-dl="' + esc(b.name) + '" style="cursor:pointer">下载</a></div>';
    }).join('') : notice('还没有平台备份。建议立即生成一份，并在迁移前再生成一份。');
    var backupCard = '<div class="card">' + cardHead('平台备份', '包含 SQLite、设备凭据密钥、TLS 证书、配置备份和审计数据', '') +
      backupList +
      (canEdit ? '<div class="btn-group" style="justify-content:flex-end;margin-top:10px">' +
        '<button class="btn btn-primary sm" id="stBackup">' + icon('download', 14) + '立即生成备份</button></div>' : '') +
      '<div class="kpi-trend">备份保存在数据卷 platform-backups/。HCI 迁移前请下载一份到独立存储。</div></div>';

    var cs = collect.settings || {};
    var lastRun = collect.last_run || {};
    var collectCard = can('sync') ? ('<div class="card">' + cardHead('采集（本平台自带采集 · 华为 VRP + 服务器）',
      '采集设置、任务历史与逐台日志都挪到「资产与采集 → 设备采集」页了，这里只留个状态。', '') +
      statList([
        { name: '台账设备 / 凭据就绪', value: (collect.devices_total || 0) + ' / ' + (collect.credential_ready || 0) },
        { name: '最近采集', value: (lastRun.finished_at || collect.last_collect_at || '尚未采集') },
        { name: '上次结果', value: lastRun.message || '—' }
      ]) + '<div class="btn-group" style="justify-content:flex-end;margin-top:10px">' +
      '<a class="btn btn-primary sm" href="#/pending">去设备采集中心</a></div></div>') : '';

    var notify = '<div class="card">' + cardHead('取数链路说明', '', '') +
      '<div style="display:flex;flex-direction:column;gap:10px">' +
      toggleRow('只读采集设备', '本平台用只读命令 SSH 采集华为交换机与 Linux / Windows 服务器，不做配置变更', true) +
      toggleRow('采集结果本地留档', '巡检、监控、告警、配置备份与命令回显都写在本平台库里，断网也能出报告', true) +
      toggleRow('导出即归档', '归档保存原始文件与 SHA256，后续下载保持当时内容不变', true) +
      '</div></div>';

    var settingsBody;
    if (settingsTab === 'datasource') settingsBody = conn;
    else if (settingsTab === 'diagnostics') settingsBody = diagCard;
    else if (settingsTab === 'backup') settingsBody = backupCard;
    else settingsBody = basic;
    return head + settingsTabs + sourceNotice(data.source_info, data.source) +
      (canEdit ? '' : notice('当前角色（' + (STATE.perms.role_label || '') + '）只能查看系统设置；'
                             + '修改数据源、采集与远程策略需要超级管理员权限。')) + settingsBody;
  }

  function bindSettings() {
    var settingsRefresh = document.getElementById('stRefresh');
    if (settingsRefresh) settingsRefresh.addEventListener('click', route);
    Array.prototype.forEach.call(document.querySelectorAll('[data-settings-tab]'), function (tab) {
      tab.addEventListener('click', function () {
        STATE.settingsTab = tab.getAttribute('data-settings-tab');
        route();
      });
    });
    var orgInput = document.getElementById('stOrgName');
    if (orgInput) orgInput.addEventListener('input', function () {
      var preview = document.getElementById('orgPreview');
      if (preview) preview.textContent = orgInput.value.trim() || '未设置';
    });
    var save = function () {
      var byId = function (id) { return document.getElementById(id); };
      var payload = {
        site_name: (byId('stSiteName') || {}).value,
        org_name: (byId('stOrgName') || {}).value,
        period_days: (byId('stPeriod') || {}).value
      };
      if (byId('stCacheTtl')) payload.cache_ttl = byId('stCacheTtl').value;
      window.NetInspect.saveSettings(payload).then(function (res) {
        STATE.status = res.settings;
        var saved = (res.settings && res.settings.settings) || {};
        STATE.meta = STATE.meta || {};
        if (saved.org_name) STATE.meta.org_name = saved.org_name;
        if (saved.site_name) STATE.meta.site_name = saved.site_name;
        showToast('设置已保存，已同步到全平台');
        route();
      }).catch(function (err) { showToast('保存失败：' + err.message); });
    };
    ['stSave', 'stSave2'].forEach(function (id) {
      var btn = document.getElementById(id);
      if (btn) btn.addEventListener('click', save);
    });
    var clSave = document.getElementById('clSave');
    if (clSave) clSave.addEventListener('click', function () {
      window.NetInspect.saveCollectSettings({
        enabled: (document.getElementById('clEnabled') || {}).value,
        interval_minutes: (document.getElementById('clInterval') || {}).value,
        concurrency: (document.getElementById('clConcurrency') || {}).value,
        timeout: (document.getElementById('clTimeout') || {}).value,
        with_config: (document.getElementById('clWithConfig') || {}).value,
        alert_cooldown_hours: (document.getElementById('clCooldown') || {}).value
      }).then(function () { showToast('采集设置已保存'); route(); })
        .catch(function (err) { showToast('保存失败：' + err.message); });
    });
    var stBackup = document.getElementById('stBackup');
    if (stBackup) stBackup.addEventListener('click', function () {
      stBackup.textContent = '备份中…';
      window.NetInspect.runSystemBackup().then(function (res) {
        showToast('平台备份已生成：' + ((res.backup || {}).name || ''));
        route();
      }).catch(function (err) {
        stBackup.innerHTML = icon('download', 14) + '立即生成备份';
        showToast('备份失败：' + err.message);
      });
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-backup-dl]'), function (node) {
      node.addEventListener('click', function () {
        download(window.NetInspect.systemBackupDownloadUrl(node.getAttribute('data-backup-dl')), { ext: 'zip' });
      });
    });

 }
  /* ---------- 登录页（原型保留） ---------- */
  /* ---------- 登录页（真实登录，对接 /api/auth/login） ---------- */
  function pageLogin(message, tone) {
    var status = STATE.authStatus || {};
    var brandMeta = siteParts();
    var brand =
      '<div class="brand-row"><div class="brand-logo" style="background:rgba(255,255,255,.18)">' + icon('gauge', 18) + '</div>' +
      '<div class="brand-text"><span class="nm" title="' + esc(brandMeta.full) + '">' + esc(brandMeta.full) + '</span></div></div>' +
      '<div class="side-spacer"></div>' +
      '<div class="points">' +
      '<span class="badge">纯本地采集 · SSH 只读巡检</span>' +
      '<h2 class="hero-title">让每一次巡检<br/>都有据可依</h2>' +
      '<p class="hero-desc">巡检数据展示、设备台账、远程运维与报表导出，一个平台管住网络设备</p>' +
      '<div class="points" style="gap:20px">' +
      '<div class="point"><span class="pt">数据来自本平台自带采集</span><span class="pd">只读 SSH 采集交换机与服务器，结果落本地库，不依赖外部平台</span></div>' +
      '<div class="point"><span class="pt">远程运维全程留痕</span><span class="pd">远程登录逐条命令留痕，变更类命令需确认、破坏性命令直接拦截</span></div>' +
      '<div class="point"><span class="pt">账号与角色</span><span class="pd">超级管理员 / 运维工程师 / 只读用户，按角色控制写操作</span></div>' +
      '</div></div>' +
      '<div class="side-spacer"></div>' +
      '<div class="data-row">' +
      '<div class="data-cell"><span class="dv" id="lgAccounts">' + (status.accounts || 0) + '</span><span class="dl">平台账号</span></div>' +
      '<div class="data-cell"><span class="dv">3</span><span class="dl">角色分级</span></div>' +
      '<div class="data-cell"><span class="dv">' + (STATE.days || 7) + '</span><span class="dl">默认统计天数</span></div>' +
      '</div>';

    var form =
      '<div class="login-card">' +
      '<div><h1 class="form-title">登录控制台</h1>' +
      '<p class="form-sub">请使用平台分配的账号登录（账号由超级管理员在「用户与权限」里创建）</p></div>' +
      (message ? notice(message, tone === 'danger' ? 'danger' : '') : '') +
      '<div class="field"><label>企业账号</label>' +
      '<div class="input"><input id="lgUser" type="text" value="' + esc(STATE.lastUser || '') + '" placeholder="账号" autocomplete="username" style="' + CTRL + '"/></div></div>' +
      '<div class="field"><label>登录密码</label>' +
      '<div class="input"><input id="lgPass" type="password" placeholder="登录口令" autocomplete="current-password" style="' + CTRL + '"/></div></div>' +
      '<div class="pwd-row">' +
      '<label class="radio" style="font-size:13px;color:var(--text-2)">' +
      '<input id="lgRemember" type="checkbox" style="width:14px;height:14px"/> 记住我（30 天免登录）</label>' +
      '<a class="link" id="lgHelp">忘记密码？</a></div>' +
      '<button class="btn btn-primary" id="doLogin" style="height:44px;font-size:15px">登 录</button>' +
      '<div class="kpi-trend" id="lgHint">' +
      (status.has_accounts ? '首次登录请使用管理员分配的账号' : '系统还没有账号：首次启动会自动创建管理员（见后端日志 / data/initial_admin_password.txt）') +
      '</div>' +
      '<p class="copyright">LinScopePlatform v1.3.0 · 数据链路：页面 → FastAPI → 本地采集库 · 登录行为会留痕</p>' +
      '</div>';

    return '<div class="login-wrap">' +
      '<section class="login-brand">' + brand + '</section>' +
      '<section class="login-form">' + form + '</section>' +
      '</div>';
  }

  function bindLogin() {
    var user = document.getElementById('lgUser');
    var pass = document.getElementById('lgPass');
    var remember = document.getElementById('lgRemember');
    var submit = function () {
      var name = (user && user.value || '').trim();
      var secret = (pass && pass.value) || '';
      if (!name || !secret) { showToast('请填写账号与口令'); return; }
      var btn = document.getElementById('doLogin');
      if (btn) { btn.textContent = '登录中…'; btn.disabled = true; }
      STATE.lastUser = name;                    // 先记住账号：登录失败重绘时不会把账号清空
      try { localStorage.setItem('ni-last-user', name); } catch (e) {}
      window.NetInspect.login(name, secret, !!(remember && remember.checked)).then(function (res) {
        window.NetInspect.setToken(res.token || '');      // 令牌存本地，后续请求自动带上
        STATE.user = res.user;
        STATE.perms = (res.overview || {}).permissions || {};
        STATE.overview = res.overview || {};
        STATE.lastUser = name;
        showToast('欢迎，' + (res.user.display_name || res.user.username));
        var next = STATE.nextHash || '#/overview';
        STATE.nextHash = '';
        if (location.hash === next) route(); else location.hash = next;
      }).catch(function (err) {
        if (btn) { btn.textContent = '登 录'; btn.disabled = false; }
        renderLogin(err.message || '登录失败', 'danger');
      });
    };
    var btn = document.getElementById('doLogin');
    if (btn) btn.addEventListener('click', submit);
    [user, pass].forEach(function (node) {
      if (node) node.addEventListener('keydown', function (e) { if (e.key === 'Enter') submit(); });
    });
    var help = document.getElementById('lgHelp');
    if (help) help.addEventListener('click', function () {
      showToast('口令由管理员在「用户与权限 → 重置口令」里重新设置');
    });
    if (user && user.value && pass) { pass.focus(); } else if (user) { user.focus(); }
  }

  function renderLogin(message, tone) {
    document.body.innerHTML = '<div id="app"></div>';
    var app = document.getElementById('app');
    app.className = '';
    app.innerHTML = pageLogin(message, tone);
    document.title = siteParts().name;
    bindLogin();
  }

  /* ---------- 会话引导：没登录就停在登录页 ---------- */
  function bootstrapAuth() {
    if (!window.NetInspect.token()) { STATE.authReady = true; return Promise.resolve(null); }
    return window.NetInspect.me().then(function (data) {
      STATE.user = data.user;
      STATE.perms = data.permissions || {};
      STATE.overview = data;
      STATE.authReady = true;
      if (!STATE.meta) {
        return window.NetInspect.meta().then(function (meta) {
          STATE.meta = meta;
          if (meta.period_days) STATE.days = Number(meta.period_days) || STATE.days;
          return data;
        }).catch(function () { return data; });
      }
      return data;
    }).catch(function () {
      window.NetInspect.setToken('');
      STATE.user = null;
      STATE.authReady = true;
      return null;
    });
  }

  function logout() {
    window.NetInspect.logout().catch(function () {}).then(function () {
      window.NetInspect.setToken('');
      STATE.user = null;
      STATE.perms = {};
      closeOverlay();
      STATE.nextHash = '';
      location.hash = '#/login';
      renderLogin('已退出登录');
    });
  }

  function can(perm) {
    return !!(STATE.perms && STATE.perms[perm]);
  }

  /* ---------- 左下角账号卡片（动态）---------- */
  function userCardHtml() {
    var user = STATE.user || { username: '', display_name: '未登录', role_label: '' };
    var name = user.display_name || user.username || '未登录';
    var initial = name.slice(0, 1);
    return '<div class="user-card" id="userCard" style="cursor:pointer" title="账号信息 / 修改口令 / 退出登录">' +
      '<div class="avatar sm">' + esc(initial) + '</div>' +
      '<div class="user-meta"><span class="user-name">' + esc(name) + '</span>' +
      '<span class="user-role">' + esc(user.role_label || '') + '</span></div>' +
      '<span style="margin-left:auto;color:var(--text-3)">' + icon('chevron', 14) + '</span></div>';
  }

  function bindUserCard() {
    var card = document.getElementById('userCard');
    if (!card) return;
    card.addEventListener('click', openAccountModal);
  }

  function openAccountModal() {
    var user = STATE.user || {};
    var overview = STATE.overview || {};
    var session = overview.session || {};
    var perms = STATE.perms || {};
    var actions = [
      { name: '可查看数据', value: perms.read ? '是' : '否' },
      { name: '可导出报表', value: perms.export ? '是' : '否' },
      { name: '台账 / 导入 / 采集', value: perms.ledger_write ? '允许' : '不允许' },
      { name: '远程控制台', value: perms.remote ? (perms.remote_full ? '全权限（命令全留痕）' : '受策略控制') : '不允许' },
      { name: '系统设置', value: perms.settings ? '允许' : '不允许' },
      { name: '账号管理', value: perms.users ? '允许' : '不允许' }
    ];
    var inner =
      '<div class="modal" style="width:640px">' +
      '<div class="card-head" style="margin-bottom:14px"><div class="t">' +
      '<div class="title" style="font-size:18px">账号信息</div>' +
      '<div class="sub">登录状态、角色权限与口令修改都在这里</div></div>' +
      '<button class="icon-btn" id="acClose" style="width:32px;height:32px">' + icon('close', 16) + '</button></div>' +
      '<div class="summary-bar"><div class="avatar">' + esc((user.display_name || user.username || '?').slice(0, 1)) + '</div>' +
      '<div class="info"><span class="n">' + esc(user.display_name || user.username || '') + ' · ' + esc(user.role_label || '') + '</span>' +
      '<span class="m">' + esc(user.username || '') + ' · 最近登录 ' + esc((overview.last_login || {}).at || '—') +
      ' · 来源 ' + esc((overview.last_login || {}).ip || '—') + '</span></div>' +
      '<span style="margin-left:auto">' + tag(perms.role_label || '', 'brand') + '</span></div>' +
      '<div class="form-row">' +
      '<div style="flex:1">' + cardHead('本账号权限', '', '') + statList(actions) + '</div>' +
      '<div style="flex:1">' + cardHead('当前会话', '', '') + statList([
        { name: '登录时间', value: session.created_at || '—' },
        { name: '会话到期', value: session.expires_at || '—' },
        { name: '来源 IP', value: session.client_ip || '—' }
      ]) + '</div></div>' +
      '<div style="font-size:12px;color:var(--text-3);margin-top:4px">修改登录口令</div>' +
      '<div class="form-row">' +
      field('原口令', plainBox('acOld', '', 'password')) +
      field('新口令（≥8 位，含两类字符）', plainBox('acNew', '', 'password')) +
      '</div>' +
      '<div class="form-row">' +
      field('确认新口令', plainBox('acNew2', '', 'password')) +
      '<div class="field"><label>&nbsp;</label><button class="btn btn-ghost" id="acSavePass">修改口令</button></div>' +
      '</div>' +
      '<div id="acResult"></div>' +
      '<div class="footer-bar">' +
      '<a class="danger-link" id="acLogout" style="cursor:pointer">退出登录</a>' +
      '<div class="btn-group"><button class="btn btn-ghost" id="acCancel">关闭</button>' +
      '<button class="btn btn-primary" id="acSessions">查看我的会话</button></div></div></div>';
    showOverlay(inner, false);
    var save = document.getElementById('acSavePass');
    if (save) save.addEventListener('click', function () {
      var oldPass = (document.getElementById('acOld') || {}).value || '';
      var newPass = (document.getElementById('acNew') || {}).value || '';
      var again = (document.getElementById('acNew2') || {}).value || '';
      if (newPass !== again) { showToast('两次输入的新口令不一致'); return; }
      window.NetInspect.changePassword(oldPass, newPass).then(function () {
        showToast('口令已修改，下次请用新口令登录');
        closeOverlay();
      }).catch(function (err) {
        document.getElementById('acResult').innerHTML = notice(err.message, 'danger');
      });
    });
    var out = document.getElementById('acLogout');
    if (out) out.addEventListener('click', function () { logout(); });
    var sessions = document.getElementById('acSessions');
    if (sessions) sessions.addEventListener('click', openMySessionsModal);
  }

  function openMySessionsModal() {
    window.NetInspect.authSessions(can('users')).then(function (res) {
      var rows = (res.sessions || []).map(function (s) {
        return [
          { text: s.username, cls: 'strong' },
          { text: s.created_at, cls: 'mono' },
          { text: s.expires_at, cls: 'mono' },
          { text: s.client_ip || '—', cls: 'mono' },
          { text: (s.user_agent || '').slice(0, 32), cls: 'dim' },
          { html: s.active ? tag('在线', 'success') : tag('已失效', 'neutral') },
          { html: s.active ? '<a class="link" data-kill="' + esc(s.token_hint) + '" style="cursor:pointer">强制下线</a>' : '—' }
        ];
      });
      var inner =
        '<div class="drawer" style="width:760px">' +
        '<div class="card-head"><div class="t"><div class="title" style="font-size:18px">登录会话</div>' +
        '<div class="sub">' + esc(res.scope || '') + ' · 共 ' + (res.total || 0) + ' 条 · 单账号最多 ' + esc(res.limit || 5) + ' 个有效会话 · 可强制下线</div></div>' +
        '<button class="icon-btn" id="se2Close" style="width:32px;height:32px">' + icon('close', 16) + '</button></div>' +
        '<div style="overflow-x:auto">' + (rows.length ? table(
          [{ text: '账号', width: 100 }, { text: '登录时间', width: 150 }, { text: '到期', width: 150 },
           { text: '来源 IP', width: 120 }, { text: '客户端', width: 200 }, { text: '状态', width: 90 }, { text: '操作' }],
          rows) : emptyTable([{ text: '账号' }, { text: '登录时间' }, { text: '到期' }, { text: '来源 IP' },
            { text: '客户端' }, { text: '状态' }, { text: '操作' }], '没有会话记录')) + '</div>' +
        '<div class="footer-bar"><span class="kpi-trend">令牌只在浏览器本地保存，服务端只存摘要</span>' +
        '<div class="btn-group"><button class="btn btn-ghost" id="se2Cancel">关闭</button></div></div></div>';
      showOverlay(inner, true);
      Array.prototype.forEach.call(document.querySelectorAll('[data-kill]'), function (node) {
        node.addEventListener('click', function () {
          var hint = node.getAttribute('data-kill');
          window.NetInspect.revokeSession(hint).then(function () {
            showToast('已强制下线');
            openMySessionsModal();
          }).catch(function (err) { showToast('失败：' + err.message); });
        });
      });
    }).catch(function (err) { showToast('读取会话失败：' + err.message); });
  }

  /* ---------- 小工具：下载 / 提示条 ---------- */
  /* 下载：fetch 带令牌取流再存成文件。
     直接 <a href> 跳转不带 Authorization 头，加鉴权后会 401 —— 所以自己取。 */
  function fmtBytes(value) {
    var n = Number(value || 0);
    if (!isFinite(n) || n < 0) return '—';
    if (n < 1024) return Math.round(n) + ' B';
    var units = ['KB', 'MB', 'GB', 'TB'];
    var size = n / 1024;
    var index = 0;
    while (size >= 1024 && index < units.length - 1) { size /= 1024; index += 1; }
    return size.toFixed(size >= 10 ? 1 : 2) + ' ' + units[index];
  }

  function createDownloadProgress(label) {
    var controller = new AbortController();
    var started = Date.now();
    var timer = null;
    var finished = false;
    var inner =
      '<div class="modal download-progress-modal" role="dialog" aria-modal="true">' +
      '<div class="dlp-head" id="dlpHead"><div class="dlp-orb">' + icon('download', 22) + '</div>' +
      '<div class="dlp-copy"><div class="dlp-title" id="dlpTitle">正在采集并打包</div>' +
      '<div class="dlp-sub" id="dlpSub">正在连接设备并读取配置/备份，完成后会自动开始下载。</div></div>' +
      '<div class="dlp-percent" id="dlpPercent">处理中</div></div>' +
      '<div class="dlp-track"><div class="dlp-bar indeterminate" id="dlpBar"></div></div>' +
      '<div class="dlp-meta"><span id="dlpBytes">等待服务器生成 ZIP</span><span id="dlpElapsed">已等待 0 秒</span></div>' +
      '<div class="dlp-steps" id="dlpSteps">' +
      '<span class="dlp-step"><i class="dot"></i>设备采集</span>' +
      '<span class="dlp-step"><i class="dot"></i>内存打包</span>' +
      '<span class="dlp-step"><i class="dot"></i>浏览器下载</span></div>' +
      '<div class="dlp-hint" id="dlpHint">交换机执行 dis cu，服务器读取备份目录；ZIP 生成后会直接下载到本地，不占用服务器磁盘。</div>' +
      '<div class="dlp-actions"><button class="btn btn-ghost sm" id="dlpCancel" data-overlay-cancel>取消</button></div></div>';
    showOverlay(inner, false);

    var head = document.getElementById('dlpHead');
    var title = document.getElementById('dlpTitle');
    var sub = document.getElementById('dlpSub');
    var percent = document.getElementById('dlpPercent');
    var bar = document.getElementById('dlpBar');
    var bytes = document.getElementById('dlpBytes');
    var elapsed = document.getElementById('dlpElapsed');
    var hint = document.getElementById('dlpHint');
    var steps = document.querySelectorAll('#dlpSteps .dlp-step');

    function setSteps(doneCount, active) {
      Array.prototype.forEach.call(steps, function (node, index) {
        node.classList.toggle('done', index < doneCount);
        node.classList.toggle('active', active.indexOf(index) >= 0);
      });
    }

    function setElapsed() {
      if (!elapsed) return;
      var seconds = Math.max(0, Math.floor((Date.now() - started) / 1000));
      elapsed.textContent = '已等待 ' + seconds + ' 秒';
    }

    setSteps(0, [0, 1]);
    setElapsed();
    timer = setInterval(setElapsed, 1000);
    OVERLAY_DISMISS = function () { if (!finished) { try { controller.abort(); } catch (e) {} } };

    function stopTimer() {
      if (timer) { clearInterval(timer); timer = null; }
    }

    function close() {
      stopTimer();
      OVERLAY_DISMISS = null;
      closeOverlay();
    }

    return {
      signal: controller.signal,
      downloading: function (name, received, total) {
        finished = false;
        head.className = 'dlp-head';
        title.textContent = '正在下载 ZIP';
        sub.textContent = name || label;
        bar.classList.remove('indeterminate', 'done', 'error');
        setSteps(2, [2]);
        var pct = total > 0 ? Math.min(100, Math.max(0, received / total * 100)) : null;
        if (pct === null) {
          bar.classList.add('indeterminate');
          percent.textContent = '下载中';
          bytes.textContent = fmtBytes(received) + ' 已下载';
        } else {
          bar.style.width = pct.toFixed(1) + '%';
          percent.textContent = Math.floor(pct) + '%';
          bytes.textContent = fmtBytes(received) + ' / ' + fmtBytes(total);
        }
        setElapsed();
      },
      success: function (name, headers, total) {
        finished = true;
        stopTimer();
        OVERLAY_DISMISS = null;
        if (elapsed) elapsed.textContent = '总耗时 ' + Math.max(0, Math.round((Date.now() - started) / 1000)) + ' 秒';
        head.className = 'dlp-head done';
        title.textContent = '下载完成';
        sub.textContent = name || label;
        percent.textContent = '100%';
        bar.classList.remove('indeterminate', 'error');
        bar.classList.add('done');
        bar.style.width = '100%';
        bytes.textContent = fmtBytes(total);
        setSteps(3, []);
        var pkg = headers || {};
        var detail = pkg['x-package-ok'] !== undefined
          ? '成功 ' + pkg['x-package-ok'] + ' 台' +
            (Number(pkg['x-package-failed'] || 0) ? '，失败 ' + pkg['x-package-failed'] + ' 台' : '') +
            ' · 共 ' + pkg['x-package-files'] + ' 个文件'
          : '文件已保存到浏览器下载目录。';
        hint.className = 'dlp-hint success';
        hint.textContent = detail + ' 可在需要时关闭此窗口。';
        var cancel = document.getElementById('dlpCancel');
        if (cancel) cancel.textContent = '关闭';
      },
      fail: function (message) {
        finished = true;
        stopTimer();
        OVERLAY_DISMISS = null;
        if (elapsed) elapsed.textContent = '耗时 ' + Math.max(0, Math.round((Date.now() - started) / 1000)) + ' 秒';
        head.className = 'dlp-head error';
        title.textContent = '打包或下载失败';
        sub.textContent = message || '请检查设备连接、凭据和备份目录后重试。';
        percent.textContent = '失败';
        bar.classList.remove('indeterminate', 'done');
        bar.classList.add('error');
        bytes.textContent = '未完成';
        setSteps(0, []);
        hint.className = 'dlp-hint error';
        hint.textContent = '请确认设备在线、SSH 端口可达且凭据正确；如果当前仍是 10.20.x.x 演示地址，请先录入真实设备后再打包。';
        var cancel = document.getElementById('dlpCancel');
        if (cancel) cancel.textContent = '关闭';
      },
      close: close,
      aborted: function () { return finished === false && controller.signal.aborted; }
    };
  }

  function readResponseBlob(resp, onProgress) {
    var total = Number(resp.headers.get('content-length') || 0);
    if (!resp.body || !resp.body.getReader) {
      return resp.blob().then(function (blob) {
        if (onProgress) onProgress(blob.size, total || blob.size);
        return { blob: blob, received: blob.size, total: total || blob.size };
      });
    }
    var reader = resp.body.getReader();
    var chunks = [];
    var received = 0;
    if (onProgress) onProgress(0, total);
    function pump() {
      return reader.read().then(function (chunk) {
        if (chunk.done) {
          var blob = new Blob(chunks, { type: resp.headers.get('content-type') || 'application/octet-stream' });
          return { blob: blob, received: received, total: total || received };
        }
        chunks.push(chunk.value);
        received += chunk.value.length;
        if (onProgress) onProgress(received, total);
        return pump();
      });
    }
    return pump();
  }

  /* 下载：fetch 带令牌取流再存成文件。
     直接 <a href> 跳转不带 Authorization 头，加鉴权后会 401 —— 所以自己取。 */
  function download(url, options) {
    options = options || {};
    var label = options.label || '文件';
    if (!window.NetInspect.token()) { showToast('请先登录再下载'); return; }
    var progress = options.progress ? createDownloadProgress(label) : null;
    if (!progress) showToast('正在生成 ' + label + '…');
    var init = { headers: { 'Authorization': 'Bearer ' + window.NetInspect.token() } };
    if (progress) init.signal = progress.signal;
    fetch(url, init)
      .then(function (resp) {
        if (resp.status === 401) {
          if (progress) progress.close();
          window.NetInspect.setToken('');
          STATE.user = null;
          STATE.perms = {};
          STATE.authReady = true;
          renderLogin('登录状态已失效，请重新登录后重试下载', 'danger');
          throw new Error('登录已过期');
        }
        if (!resp.ok) {
          return resp.text().then(function (text) {
            var message = text;
            try { var parsed = JSON.parse(text) || {}; message = parsed.detail || parsed.error || text; } catch (e) {}
            throw new Error(message || ('HTTP ' + resp.status));
          });
        }
        var name = '';
        var disposition = resp.headers.get('Content-Disposition') || '';
        var match = /filename\*=UTF-8''([^;]+)/i.exec(disposition) || /filename="?([^";]+)"?/i.exec(disposition);
        if (match) { try { name = decodeURIComponent(match[1]); } catch (e) { name = match[1]; } }
        var headers = {};
        ['x-package-ok', 'x-package-failed', 'x-package-files'].forEach(function (key) {
          var value = resp.headers.get(key);
          if (value !== null) headers[key] = value;
        });
        if (progress) progress.downloading(name || label, 0, Number(resp.headers.get('content-length') || 0));
        var payload = progress
          ? readResponseBlob(resp, function (received, total) {
              progress.downloading(name || label, received, total);
            })
          : resp.blob().then(function (blob) { return { blob: blob, received: blob.size, total: blob.size }; });
        return payload.then(function (result) {
          return { blob: result.blob, name: name, headers: headers, total: result.total || result.blob.size };
        });
      })
      .then(function (result) {
        var name = result.name || (label + '.' + (options.ext || 'dat'));
        var objectUrl = URL.createObjectURL(result.blob);
        var a = document.createElement('a');
        a.href = objectUrl;
        a.download = name;
        a.rel = 'noopener';
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        setTimeout(function () { a.remove(); URL.revokeObjectURL(objectUrl); }, 2000);
        if (progress) {
          progress.success(name, result.headers, result.total);
        } else {
          var pkg = result.headers || {};
          if (pkg['x-package-ok'] !== undefined) {
            showToast('已下载：' + name + ' · 成功 ' + pkg['x-package-ok'] + ' 台' +
              (Number(pkg['x-package-failed'] || 0) ? '，失败 ' + pkg['x-package-failed'] + ' 台' : '') +
              ' · 文件 ' + pkg['x-package-files'] + ' 个');
          } else {
            showToast('已下载：' + name);
          }
        }
        if (options.after) { options.after(result); }
      })
      .catch(function (err) {
        var message = err && err.message ? err.message : '未知错误';
        if ((err && err.name === 'AbortError') || (progress && progress.aborted())) {
          if (progress) progress.close();
          showToast('已取消下载');
          return;
        }
        if (progress) progress.fail(message);
        else showToast('下载失败：' + message);
      });
  }
  function showToast(text) {
    var box = document.getElementById('ni-toast');
    if (!box) {
      box = document.createElement('div');
      box.id = 'ni-toast';
      box.style.cssText = 'position:fixed;right:24px;bottom:24px;z-index:99;display:flex;flex-direction:column;gap:8px';
      document.body.appendChild(box);
    }
    var item = document.createElement('div');
    item.className = 'notice';
    item.style.cssText = 'background:var(--surface);color:var(--text-1);border:1px solid var(--border);box-shadow:0 8px 24px rgba(0,0,0,.12);max-width:420px;font-size:12px';
    item.innerHTML = '<span>' + esc(text) + '</span>';
    box.appendChild(item);
    setTimeout(function () { item.remove(); }, 5000);
  }

  /* ---------- 弹窗 / 抽屉（沿用原型结构） ---------- */
  function closeOverlay() {
    var o = document.getElementById('overlay');
    if (o) o.remove();
  }

  function showOverlay(inner, drawer) {
    closeOverlay();
    var wrap = document.createElement('div');
    wrap.id = 'overlay';
    wrap.className = 'mask ' + (drawer ? 'overlay-drawer' : 'overlay-center');
    wrap.innerHTML = inner;
    wrap.addEventListener('mousedown', function (e) {
      if (e.target === wrap) dismissOverlay();
    });
    // 遮罩内按 Esc 也要能关：终端（xterm）会吞键盘事件，所以焦点必须进弹窗
    wrap.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { e.preventDefault(); dismissOverlay(); }
    });
    document.body.appendChild(wrap);
    var focusTarget = wrap.querySelector('[data-autofocus]') ||
      wrap.querySelector('.dialog .btn, .modal input, .modal textarea, .drawer input, .drawer .btn, .mask .btn');
    if (focusTarget && focusTarget.focus) {
      try { focusTarget.focus(); } catch (e) {}
    } else {
      wrap.setAttribute('tabindex', '-1');
      try { wrap.focus(); } catch (e) {}
    }
  }

  

  

  

  

  /* ---------- 台账补充弹窗（本平台自己的数据） ---------- */
  function openLedger(key) {
    window.NetInspect.device(key).then(function (data) {
      var dev = data.device || {};
      var ledger = dev.ledger || {};
      var kinds = [{ value: '', label: '自动推断（' + (dev.type_label || '—') + '）' },
        { value: 'switch', label: '交换机' }, { value: 'core_switch', label: '核心交换机' },
        { value: 'aggregation_switch', label: '汇聚交换机' }, { value: 'access_switch', label: '接入交换机' },
        { value: 'router', label: '路由器' }, { value: 'firewall', label: '防火墙' },
        { value: 'waf', label: 'WAF' }, { value: 'ips', label: 'IPS/IDS' },
        { value: 'vpn', label: 'VPN 设备' }, { value: 'security', label: '安全设备' },
        { value: 'ac', label: '无线控制器' }, { value: 'server', label: '服务器' },
        { value: 'other', label: '其他设备' }];
      var inner =
        '<div class="modal" style="width:640px">' +
        '<div class="card-head" style="margin-bottom:14px"><div class="t">' +
        '<div class="title" style="font-size:18px">设备台账补充</div>' +
        '<div class="sub">设备身份由台账 / 采集回填，以下补充字段保存在本平台</div></div>' +
        '<button class="icon-btn" id="lgClose" style="width:32px;height:32px">' + icon('close', 16) + '</button></div>' +
        '<div class="summary-bar"><div class="avatar">' + icon('server', 18) + '</div>' +
        '<div class="info"><span class="n">' + esc(dev.name || dev.ip) + ' · ' + esc(dev.type_label || '') + '</span>' +
        '<span class="m">' + esc(dev.ip) + ' · ' + esc(dev.model || '型号未采集') + ' · 健康度 ' +
        esc(dev.health_score === null || dev.health_score === undefined ? '—' : dev.health_score) + '</span></div>' +
        '<span style="margin-left:auto">' + tag(dev.health_label || '未巡检', dev.health_tone || 'neutral') + '</span></div>' +
        '<div class="form-row">' +
        field('资产编号', plainBox('lgAsset', ledger.asset_no)) +
        field('责任人', plainBox('lgOwner', ledger.owner)) +
        '</div>' +
        '<div class="form-row">' +
        field('设备用途', plainBox('lgUsage', ledger.usage)) +
        field('设备地点', plainBox('lgLocation', ledger.location)) +
        '</div>' +
        '<div class="form-row">' +
        field('维保到期', plainBox('lgWarranty', ledger.warranty_until, 'date')) +
        field('设备类型纠正', picker('lgKind', kinds, ledger.kind_override || '')) +
        '</div>' +
        field('备注', plainBox('lgNote', ledger.note)) +
        '<div class="footer-bar"><span class="kpi-trend">最近更新：' + esc(ledger.updated_at || '尚未填写') + '</span>' +
        '<div class="btn-group"><button class="btn btn-ghost" id="lgCancel">取消</button>' +
        '<button class="btn btn-primary" id="lgSave">保存台账</button></div></div></div>';
      showOverlay(inner, false);
      var save = document.getElementById('lgSave');
      if (save) save.addEventListener('click', function () {
        save.textContent = '保存中…';
        window.NetInspect.saveLedger(dev.ip, {
          asset_no: (document.getElementById('lgAsset') || {}).value || '',
          owner: (document.getElementById('lgOwner') || {}).value || '',
          usage: (document.getElementById('lgUsage') || {}).value || '',
          location: (document.getElementById('lgLocation') || {}).value || '',
          warranty_until: (document.getElementById('lgWarranty') || {}).value || '',
          kind_override: (document.getElementById('lgKind') || {}).value || '',
          note: (document.getElementById('lgNote') || {}).value || ''
        }).then(function () {
          closeOverlay();
          showToast('台账已保存');
          route();
        }).catch(function (err) {
          save.textContent = '保存台账';
          showToast('保存失败：' + err.message);
        });
      });
    }).catch(function (err) { showToast('打开台账失败：' + err.message); });
  }
  /* ---------- 页面：远程登录 ---------- */
  var TERM = { term: null, fit: null, ws: null, ip: '', session: null, commands: [], connected: false };

  function pageRemote(data) {
    var devices = data.devices || [];
    var stats = data.sessions || {};
    var target = STATE.remote.ip || '';
    var policy = data.policy || {};
    var deps = data.dependencies || {};
    var currentCategory = STATE.remote.category || 'switch';
    if (target) {
      var targetDevice = devices.filter(function (d) { return d.ip === target; })[0];
      if (targetDevice) currentCategory = targetDevice.category || currentCategory;
    }
    STATE.remote.category = currentCategory;
    var categories = data.categories || {};
    var categoryDefs = [
      { key: 'switch', label: '交换机', icon: 'network', desc: '核心 / 汇聚 / 接入 / 路由' },
      { key: 'server', label: '服务器', icon: 'server', desc: 'Linux / Windows 主机' },
      { key: 'security', label: '安全设备', icon: 'lock', desc: '防火墙 / VPN / WAF / IPS' }
    ];
    var filtered = devices.filter(function (d) { return (d.category || 'switch') === currentCategory; });
    if (target && !filtered.some(function (d) { return d.ip === target; })) target = '';
    var categoryInfo = categories[currentCategory] || {
      label: (categoryDefs.filter(function (c) { return c.key === currentCategory; })[0] || {}).label || '',
      total: filtered.length,
      credential_ready: filtered.filter(function (d) { return d.credential && d.credential.configured; }).length
    };
    var validTabs = ['terminal', 'devices', 'status', 'commands', 'sessions'];
    var tab = validTabs.indexOf(STATE.remote.tab) >= 0 ? STATE.remote.tab : 'terminal';
    STATE.remote.tab = tab;

    var head =
      topbar('搜索设备名称 / IP / 责任人 / 告警') +
      '<div class="page-head"><div class="page-title"><h1>远程控制台 · 跳板机</h1>' +
      '<div class="page-sub"><span>浏览器 → 平台跳板机 → 设备 · SSH + SFTP · ' + devices.length + ' 台设备 · 凭据就绪 ' + (data.credential_ready || 0) +
      ' 台 · 历史会话 ' + (stats.total || 0) + ' 次</span>' +
      '<span>' + (can('remote_full') ? '当前账号：全权限直通（命令全留痕）' : '当前账号：命令策略 ' + esc(policyLabel(policy.mode))) + '</span></div></div>' +
      '<div class="cta-row"><button class="btn btn-ghost" id="rmPolicy">命令策略</button>' +
      '<button class="btn btn-primary" id="rmRefresh">' + icon('refresh', 14) + '刷新</button></div></div>';

    var noticeHtml = '';
    if (!can('remote')) noticeHtml += notice('当前角色（' + (STATE.perms.role_label || '') +
      '）只能查看，不能开远程会话；需要「运维工程师」及以上角色。', 'danger');
    if (!deps.paramiko || !deps.cryptography) {
      noticeHtml = notice('缺少 Python 依赖（' + (!deps.paramiko ? 'paramiko ' : '') +
        (!deps.cryptography ? 'cryptography' : '') + '）：在后端跑 pip install -r requirements.txt 后重启即可。', 'danger');
    }

    var categoryStrip = '<div class="console-cat-grid module-category-strip">' + categoryDefs.map(function (cat) {
      var info = categories[cat.key] || { total: devices.filter(function (d) { return d.category === cat.key; }).length,
        credential_ready: devices.filter(function (d) { return d.category === cat.key && d.credential && d.credential.configured; }).length };
      return '<button class="console-cat' + (cat.key === currentCategory ? ' active' : '') + '" data-console-cat="' + cat.key + '">' +
        '<span class="console-cat-ico">' + icon(cat.icon, 19) + '</span>' +
        '<span class="console-cat-copy"><strong>' + esc(cat.label) + '</strong><small>' + esc(cat.desc) + '</small></span>' +
        '<span class="console-cat-count"><b>' + esc(info.total || 0) + '</b><small>凭据 ' + esc(info.credential_ready || 0) + '/' + esc(info.total || 0) + '</small></span></button>';
    }).join('') + '</div>';

    var kpis = [
      { label: '设备总数', value: String(devices.length), unit: '台', note: '交换机 / 服务器 / 安全设备统一入口', tone: 'default' },
      { label: '凭据就绪', value: String(data.credential_ready || 0), unit: '台', note: data.credential_missing ? (data.credential_missing + ' 台还没配凭据') : '全部已配置', tone: data.credential_missing ? 'warning' : 'success' },
      { label: '历史会话', value: String(stats.total || 0), unit: '次', note: '运行中 ' + (stats.running || 0) + ' · 失败 ' + (stats.failed || 0), tone: 'default' },
      { label: '当前板块', value: String(categoryInfo.total || 0), unit: '台', note: categoryInfo.label + ' · 在线 ' + filtered.filter(function (d) { return d.online; }).length + ' 台', tone: 'default' }
    ];

    var pickerOptions = filtered.map(function (d) {
      return { value: d.ip, label: d.name + '（' + d.type_label + ' · ' + d.ip + '）' + (d.credential.configured ? '' : ' — 未配凭据') };
    });
    var modeText = can('remote_full') ? '全权限终端' : policyLabel(policy.mode);
    var consoleCard = '<div class="card overview-module-card">' +
      cardHead('设备登录（跳板机）', '浏览器不直连设备，由本平台跳板机统一建立 SSH 会话；凭据、策略、审计与 SFTP 全局共用',
        '<span class="chip' + (can('remote_full') ? ' success' : '') + '" id="rmStatus">' + esc(modeText) + ' · 未连接</span>') +
      categoryStrip +
      '<div class="form-row">' + field('目标设备（' + categoryInfo.label + '）', picker('rmDevice', pickerOptions, target, filtered.length ? '' : '当前板块暂无可登录设备')) +
      field('登录账号', input('（连接后显示）')) + '</div>' +
      '<div class="btn-group module-action-row">' +
      '<button class="btn btn-primary" id="rmConnect">' + icon('terminal', 14) + '登录设备</button>' +
      '<button class="btn btn-ghost" id="rmSftp">SFTP 文件管理</button>' +
      '<button class="btn btn-ghost" id="rmDisconnect" disabled>断开</button>' +
      '<button class="btn btn-ghost" id="rmCred">配置凭据</button>' +
      '<button class="btn btn-ghost" id="rmTest">测试连接</button>' +
      '<button class="btn btn-ghost" id="rmClear">清屏</button>' +
      '<button class="btn btn-ghost" id="rmCopy">复制会话日志</button></div>' +
      '<div id="termHost" style="height:460px;border-radius:12px;overflow:hidden;background:#0f1420;padding:8px"></div>' +
      '<div class="kpi-trend" id="rmHint">' + (can('remote_full')
        ? '超级管理员使用全权限直通：不再二次拦截命令，但每条命令、每次连接和 SFTP 操作仍会完整留痕。'
        : '命令会按全局策略执行：变更类命令需确认，破坏性命令直接拦截。') + '</div></div>';

    var deviceView = clientPage(filtered, STATE.remote, 'device_page', 'device_size', [10, 20, 50], 10);
    var rows = deviceView.rows.map(function (d) {
      var cred = d.credential || {};
      return [
        { text: d.name, cls: 'strong' }, { text: d.ip, cls: 'mono' }, { text: d.type_label }, { text: d.group || '—' },
        { html: '<span class="status-text ' + (d.online ? 'success' : 'danger') + '">' + (d.online ? '在线' : '离线') + '</span>' },
        { html: cred.configured ? tag('已配置', 'success') : tag('未配置', 'warning') },
        { html: '<a class="link" data-act="connect" data-ip="' + esc(d.ip) + '" style="cursor:pointer">登录</a>' +
            ' · <a class="link" data-act="sftp" data-ip="' + esc(d.ip) + '" style="cursor:pointer">SFTP</a>' +
            ' · <a class="link" data-act="cred" data-ip="' + esc(d.ip) + '" style="cursor:pointer">凭据</a>' +
            ' · <a class="link" data-act="test" data-ip="' + esc(d.ip) + '" style="cursor:pointer">测试</a>' }
      ];
    });
    var devicesCard = '<div class="card tight overview-module-card">' +
      cardHead(categoryInfo.label + '设备入口', '当前板块 ' + filtered.length + ' 台；SSH / SFTP 共用设备凭据与操作审计', '') +
      categoryStrip + '<div style="overflow-x:auto">' + (rows.length ? table(
        [{ text: '设备名称', width: 170 }, { text: 'IP 地址', width: 130 }, { text: '设备类型', width: 120 },
         { text: '所在分组', width: 110 }, { text: '在线', width: 80 }, { text: '凭据', width: 190 }, { text: '操作', width: 210 }], rows)
        : emptyTable([{ text: '设备名称' }, { text: 'IP 地址' }, { text: '设备类型' }, { text: '所在分组' },
          { text: '在线' }, { text: '凭据' }, { text: '操作' }], '当前板块没有设备；可在设备清单新增或调整设备类型')) + '</div>' +
      pagerFooter('rmDevices', deviceView, '台') + '</div>';

    var statusCard = '<div class="card overview-module-card">' + cardHead('当前会话状态', 'SSH / SFTP / 凭据 / 策略 / 审计统一状态',
        tag(can('remote_full') ? '全权限' : '受控', can('remote_full') ? 'success' : 'brand')) +
      '<div id="rmSessionInfo">' + statList([
        { name: '设备', value: target || '未选择' },
        { name: '状态', value: TERM.connected ? '已连接' : '未连接' },
        { name: '登录账号', value: (TERM.session || {}).username || '—' },
        { name: '权限模式', value: modeText },
        { name: '已发命令', value: String(TERM.sent || 0) },
        { name: '拦截 / 取消', value: String(TERM.blocked || 0) },
        { name: '凭据存储', value: '本平台加密保管' },
        { name: '操作留痕', value: 'SSH + SFTP 全审计' }
      ]) + '</div><div class="footer-bar"><span class="kpi-trend">命令与会话均落库留痕，可按时间追责</span>' +
      '<button class="btn btn-ghost sm" data-go-console="1">返回终端</button></div></div>';

    var commandsCard = '<div class="card overview-module-card">' + cardHead('本次命令留痕', '每敲一条记一条，最多显示最近 40 条', '') +
      '<div id="rmCommandLog" class="module-scroll-list">' + notice('连接后这里会实时显示命令与拦截记录') + '</div></div>';

    var sessionList = stats.sessions || [];
    var sessionView = clientPage(sessionList, STATE.remote, 'session_page', 'session_size', [10, 20, 50], 10);
    var sessionsCard = '<div class="card tight overview-module-card">' + cardHead('历史会话', '点一条查看当时敲了什么 · 共 ' + sessionList.length + ' 次', '') +
      (sessionView.rows.length ? '<div class="stat-list">' + sessionView.rows.map(function (s) {
        return '<div class="stat-item" data-session="' + s.id + '" style="cursor:pointer"><span class="n">' +
          esc(s.device_name || s.device_ip) + ' · ' + esc(s.username) + '</span><span class="v">' + esc(s.started_at) +
          ' · 命令 ' + (s.commands || 0) + ' · 拦截 ' + (s.blocked || 0) + ' · ' + esc(sessionStatusLabel(s.status)) + '</span></div>';
      }).join('') + '</div>' : notice('还没有会话记录')) +
      pagerFooter('rmSessionsPage', sessionView, '次') + '</div>';

    var tabs = moduleTabs([
      { key: 'terminal', label: '终端会话', icon: 'terminal', count: filtered.length },
      { key: 'devices', label: '设备入口', icon: 'server', count: filtered.length },
      { key: 'status', label: '会话状态', icon: 'gauge' },
      { key: 'commands', label: '命令留痕', icon: 'file' },
      { key: 'sessions', label: '历史会话', icon: 'archive', count: sessionList.length }
    ], tab, 'remote-tab', '<span>按标签页切换远程运维功能</span>');

    var body = tab === 'devices' ? devicesCard : tab === 'status' ? statusCard : tab === 'commands' ? commandsCard : tab === 'sessions' ? sessionsCard : consoleCard;
    return head + noticeHtml + kpiCards(kpis, true) + sourceNotice(data.source_info, data.source) + tabs + body;
  }

  function policyLabel(mode) {
    return { confirm: '变更类命令需确认', block: '只放行查看类命令', off: '不拦截（仅留痕）', full: '全权限直通（仅留痕）' }[mode] || mode || '—';
  }

  function sessionStatusLabel(status) {
    return { running: '进行中', closed: '已结束', timeout: '超时断开', error: '异常结束' }[status] || status || '';
  }

  function remoteQuery() {
    var r = STATE.remote || {};
    var parts = ['category=' + encodeURIComponent(r.category || 'switch'), 'tab=' + encodeURIComponent(r.tab || 'terminal')];
    if (r.ip) parts.push('device=' + encodeURIComponent(r.ip));
    parts.push('device_page=' + (r.device_page || 1));
    parts.push('device_size=' + (r.device_size || 10));
    parts.push('session_page=' + (r.session_page || 1));
    parts.push('session_size=' + (r.session_size || 10));
    return parts.join('&');
  }

  function remoteApplyQuery(query) {
    if (!query) return;
    STATE.remote.ip = query.device || '';
    if (['switch', 'server', 'security'].indexOf(query.category) >= 0) STATE.remote.category = query.category;
    if (['terminal', 'devices', 'status', 'commands', 'sessions'].indexOf(query.tab) >= 0) STATE.remote.tab = query.tab;
    else STATE.remote.tab = query.device ? 'terminal' : 'devices';
    if (query.device_page !== undefined) STATE.remote.device_page = Number(query.device_page) || 1;
    if (query.session_page !== undefined) STATE.remote.session_page = Number(query.session_page) || 1;
    if ([10,20,50].indexOf(Number(query.device_size)) >= 0) STATE.remote.device_size = Number(query.device_size);
    if ([10,20,50].indexOf(Number(query.session_size)) >= 0) STATE.remote.session_size = Number(query.session_size);
  }

  /* ---------- 控制台：xterm ↔ WebSocket ---------- */
  function termFit() {
    if (TERM.fit) { try { TERM.fit.fit(); } catch (e) {} }
    if (TERM.term && TERM.ws && TERM.ws.readyState === 1) {
      try { TERM.ws.send(JSON.stringify({ type: 'resize', cols: TERM.term.cols, rows: TERM.term.rows })); } catch (e) {}
    }
  }

  function termWrite(text, color) {
    if (!TERM.term) return;
    if (color) { TERM.term.writeln('\r\n\x1b[' + color + 'm' + text + '\x1b[0m'); }
    else { TERM.term.write(text); }
  }

  function termStatus(text, tone) {
    var chip = document.getElementById('rmStatus');
    if (chip) { chip.textContent = text; chip.className = 'chip' + (tone ? ' ' + tone : ''); }
    var btn = document.getElementById('rmDisconnect');
    if (btn) btn.disabled = !TERM.connected;
  }

  function renderSessionInfo() {
    var host = document.getElementById('rmSessionInfo');
    if (!host) return;
    var s = TERM.session || {};
    host.innerHTML = statList([
      { name: '设备', value: (s.device_name || TERM.ip || '—') + (TERM.ip ? '（' + TERM.ip + '）' : '') },
      { name: '登录账号', value: s.username || '—' },
      { name: '权限模式', value: s.unrestricted ? '全权限（命令全留痕）' : policyLabel(s.policy) },
      { name: '状态', value: TERM.connected ? '已连接' : '未连接' },
      { name: '开始时间', value: TERM.startedAt || '—' },
      { name: '已发命令', value: String(TERM.sent || 0) },
      { name: '拦截 / 取消', value: String(TERM.blocked || 0) }
    ]);
  }

  function renderCommandLog() {
    var host = document.getElementById('rmCommandLog');
    if (!host) return;
    if (!TERM.commands.length) { host.innerHTML = notice('连接后这里会实时显示命令与拦截记录'); return; }
    host.innerHTML = '<div class="stat-list">' + TERM.commands.slice(-40).reverse().map(function (c) {
      var tone = c.action === 'sent' ? 'success' : c.action === 'block' ? 'danger' : 'warning';
      return '<div class="stat-item" style="height:auto;padding:8px 0;flex-direction:column;align-items:flex-start;gap:3px">' +
        '<span class="mono" style="font-size:12px;color:var(--text-1);white-space:normal">' + esc(c.command) + '</span>' +
        '<span class="kpi-trend">' + esc(c.created_at || '') + ' · ' + tag(c.action === 'sent' ? '已下发' : (c.action === 'block' ? '已拦截' : '已取消'), tone) + '</span></div>';
    }).join('') + '</div>';
  }

  function remoteConnect(ip) {
    if (!ip) { showToast('请先选择目标设备'); return; }
    var device = (STATE.remoteDevices || []).filter(function (d) { return d.ip === ip; })[0] || {};
    if (!(device.credential || {}).configured) {
      showToast('首次登录需要先配置该设备的 SSH 账号和口令/私钥');
      openCredentialModal(ip, true);
      return;
    }
    if (!window.Terminal) { showToast('终端组件未加载（assets/vendor/xterm 缺失）'); return; }
    remoteDisconnect(true);
    TERM.ip = ip;
    STATE.remote.ip = ip;
    TERM.commands = [];
    TERM.sent = 0;
    TERM.blocked = 0;
    TERM.startedAt = new Date().toLocaleTimeString('zh-CN', { hour12: false });
    var host = document.getElementById('termHost');
    if (!host) return;
    host.innerHTML = '';
    TERM.term = new window.Terminal({
      fontSize: 13, fontFamily: 'JetBrains Mono, Consolas, monospace',
      cursorBlink: true, scrollback: 3000, convertEol: false,
      theme: { background: '#0f1420', foreground: '#d7dce5', cursor: '#4c8dff', selectionBackground: '#20406e' }
    });
    TERM.fit = new window.FitAddon.FitAddon();
    TERM.term.loadAddon(TERM.fit);
    TERM.term.open(host);
    termFit();
    TERM.term.writeln('\x1b[36m正在建立到 ' + ip + ' 的 SSH 会话…\x1b[0m');
    termStatus('连接中…', '');

    var ws = new WebSocket(window.NetInspect.wsUrl('/remote/session/' + encodeURIComponent(ip) + (can('remote_full') ? '?mode=full' : '')));
    TERM.ws = ws;
    ws.onopen = function () { termFit(); };
    ws.onmessage = function (event) {
      var msg = {};
      try { msg = JSON.parse(event.data); } catch (e) { return; }
      if (msg.type === 'output') { termWrite(msg.data || ''); }
      else if (msg.type === 'ready') {
        TERM.connected = true; TERM.session = msg.session || {};
        termStatus((TERM.session.unrestricted ? '已连接 · 全权限' : '已连接'), 'success');
        renderSessionInfo();
      }
      else if (msg.type === 'notice') {
        var color = msg.level === 'error' ? '31' : (msg.level === 'warn' ? '33' : '36');
        termWrite(msg.text, color);
        if (msg.text && msg.text.indexOf('已拦截') === 0) { TERM.blocked += 1; renderSessionInfo(); }
      }
      else if (msg.type === 'command') {
        TERM.commands.push(msg.command || {});
        if ((msg.command || {}).action === 'sent') TERM.sent = (TERM.sent || 0) + 1;
        renderCommandLog(); renderSessionInfo();
      }
      else if (msg.type === 'confirm') { remoteConfirmModal(msg); }
      else if (msg.type === 'closed') {
        termWrite(msg.reason || '会话已结束', '33');
        TERM.connected = false; TERM.ws = null;
        termStatus('未连接', ''); renderSessionInfo();
      }
    };
    ws.onclose = function () {
      TERM.connected = false;
      termStatus('未连接', '');
      renderSessionInfo();
    };
    ws.onerror = function () { termWrite('WebSocket 连接异常（后端是否在运行？）', '31'); };
    TERM.term.onData(function (data) {
      if (TERM.ws && TERM.ws.readyState === 1) {
        TERM.ws.send(JSON.stringify({ type: 'input', data: data }));
      }
    });
    TERM.term.onResize(function () { termFit(); });
  }

  function remoteDisconnect(silent) {
    if (TERM.ws && TERM.ws.readyState === 1) {
      try { TERM.ws.send(JSON.stringify({ type: 'close' })); } catch (e) {}
      try { TERM.ws.close(); } catch (e) {}
    }
    TERM.ws = null;
    TERM.connected = false;
    termStatus('未连接', '');
    if (!silent) termWrite('已断开', '33');
    renderSessionInfo();
  }

  /* 危险命令确认：暂停终端输入，等操作员定夺 */
  function remoteConfirmModal(msg) {
    if (TERM.term) { try { TERM.term.options.disableStdin = true; } catch (e) {} }
    var inner =
      '<div class="dialog" style="width:560px">' +
      '<div class="card-head"><div class="t"><div class="title">这条命令需要确认后才会下发</div>' +
      '<div class="sub">' + esc(msg.reason || '命中命令策略') + '</div></div>' +
      '<button class="icon-btn" id="cfClose" style="width:32px;height:32px">' + icon('close', 16) + '</button></div>' +
      '<div class="summary-bar" style="background:var(--warning-soft-bg)">' + icon('alert', 18) +
      '<div class="info"><span class="n mono" style="white-space:normal">' + esc(msg.command) + '</span>' +
      '<span class="m">' + esc(TERM.ip) + '</span></div></div>' +
      '<div class="stat-list">' + statList([
        { name: '命中原因', value: msg.reason || '变更类命令' },
        { name: '放行后', value: '回车才会发给设备（命令真正执行）' },
        { name: '取消', value: '向设备发送 Ctrl+C 清掉该行，不执行' }
      ]) + '</div>' +
      '<div class="footer-bar"><span class="kpi-trend">确认期间键入的内容会被丢弃</span>' +
      '<div class="btn-group"><button class="btn btn-ghost" id="cfCancel" data-autofocus="1">取消执行</button>' +
      '<button class="btn btn-danger" id="cfOk">确认执行</button></div></div></div>';
    showOverlay(inner, false);
    var answered = false;
    var answer = function (allow) {
      if (answered) return;                       // 防止「点按钮 + 遮罩关闭」重复回执
      answered = true;
      OVERLAY_DISMISS = null;
      if (TERM.ws && TERM.ws.readyState === 1) {
        TERM.ws.send(JSON.stringify({ type: 'confirm', id: msg.id, allow: allow }));
      }
      if (TERM.term) { try { TERM.term.options.disableStdin = false; } catch (e) {} }
      try { TERM.term.focus(); } catch (e) {}
      closeOverlay();
    };
    // 叉掉 / 按 Esc / 点遮罩 = 取消执行（必须回执后端，否则终端会一直停在等待确认）
    OVERLAY_DISMISS = function () { answer(false); };
    var ok = document.getElementById('cfOk');
    if (ok) ok.addEventListener('click', function () { answer(true); });
    var cancel = document.getElementById('cfCancel');
    if (cancel) cancel.addEventListener('click', function () { answer(false); });
    var close = document.getElementById('cfClose');
    if (close) close.addEventListener('click', function () { answer(false); });
  }

  /* ---------- 凭据配置弹窗 ---------- */
  function openCredentialModal(target, autoConnect, onCollect) {
    var ips = (Array.isArray(target) ? target : [target]).filter(function (ip, i, all) { return ip && all.indexOf(ip) === i; });
    if (!ips.length) return;
    var multiple = ips.length > 1;
    var devices = ips.map(function (ip) { return (STATE.remoteDevices || []).filter(function (d) { return d.ip === ip; })[0] || { ip: ip }; });
    var device = devices[0], ip = ips[0], cred = multiple ? {} : (device.credential || {});
    var title = multiple ? '配置 ' + ips.length + ' 台设备登录凭据' : '配置设备登录凭据';
    var manualInput = function (id, type, placeholder) {
      // Device secrets belong to the SSH API, not the site's login/password manager.
      var masked = type === 'password' && window.CSS && CSS.supports('-webkit-text-security', 'disc');
      return '<div class="input"><input id="' + id + '" type="' + (masked ? 'text' : type) +
        '"' + (masked ? ' class="device-secret-input"' : '') +
        ' value="" autocomplete="off" data-lpignore="true" data-1p-ignore="true" data-bwignore="true"' +
        ' autocapitalize="none" spellcheck="false" placeholder="' + esc(placeholder) + '" style="' + CTRL + '"/></div>';
    };
    var inner = '<div class="modal credential-modal"><div id="crForm" role="group" aria-label="设备 SSH 凭据">' +
      '<div class="card-head"><div class="t"><div class="title">' + esc(title) + '</div>' +
      '<div class="sub">' + (multiple ? '手动输入端口、账号和密码，应用于所选设备。不同端口的设备请分别配置。' : '手动输入设备的 SSH 端口、账号和密码。') + '</div></div>' +
      '<button type="button" class="icon-btn" id="crClose" aria-label="关闭">' + icon('close',16) + '</button></div>' +
      '<div class="credential-targets">' + devices.map(function (d) { return '<span><b>' + esc(d.name || d.ip) + '</b><small class="mono">' + esc(d.ip) + '</small></span>'; }).join('') + '</div>' +
      '<div class="credential-main">' + field('设备登录账号', manualInput('crUser','text','手动输入设备账号')) +
      '<div class="field" id="crPasswordField"><label for="crPass">设备登录密码</label>' + manualInput('crPass','password','手动输入设备密码') + '</div></div>' +
      field('SSH 端口（必填）', manualInput('crPort','text','手动输入 SSH 端口，如 2222')) +
      '<details class="credential-options"' + (cred.auth === 'key' ? ' open' : '') + '><summary>认证选项（私钥）</summary><div class="form-row">' +
      field('认证方式', picker('crAuth', [{value:'password',label:'账号密码'},{value:'key',label:'私钥'}], cred.auth || 'password')) + '</div>' +
      '<div class="credential-key" id="crKeyFields" hidden><div class="field"><label for="crKey">私钥内容（OpenSSH 格式）</label><div class="input" style="height:auto;padding:8px 12px">' +
      '<textarea id="crKey" name="device_ssh_private_key" rows="4" autocomplete="off" placeholder="手动粘贴私钥；已保存的私钥可留空沿用" style="' + CTRL + ';resize:vertical;font-family:var(--font-mono)"></textarea></div></div>' +
      field('私钥口令（可选）',manualInput('crKeyPass','password','手动输入私钥口令')) + '</div>' +
      field('备注（可选）',plainBox('crNote',cred.note || '')) +
      (!multiple ? '<div class="credential-fingerprint"><span class="mono">' + esc(cred.host_key_fp || '尚未记录 SSH 主机指纹') + '</span>' +
        (can('settings') && cred.configured ? '<a class="link" id="crResetHostKey">重置指纹</a>' : '') + '</div>' : '') + '</details>' +
      '<div id="crResult" role="status" aria-live="polite"></div><div class="footer-bar">' +
      (!multiple && cred.configured ? '<button type="button" class="danger-link" id="crDelete">删除凭据</button>' : '<span></span>') +
      '<div class="btn-group"><button type="button" class="btn btn-ghost" id="crCancel">取消</button>' +
      '<button type="button" class="btn btn-ghost" id="crTest">' + (multiple ? '测试全部连接' : '测试连接') + '</button>' +
      '<button type="button" class="btn btn-ghost" id="crSave" disabled>保存</button>' +
      (onCollect ? '<button type="button" class="btn btn-primary" id="crSaveCollect" disabled>保存并采集' + (multiple ? '（' + ips.length + ' 台）' : '') + '</button>' : '') +
      '</div></div></div></div>';
    showOverlay(inner,false);
    var form = document.getElementById('crForm');
    form.addEventListener('submit', function (event) { event.preventDefault(); });
    var test = document.getElementById('crTest'), save = document.getElementById('crSave'), collect = document.getElementById('crSaveCollect');
    var testedSignature = '', busy = false;
    var payload = function (d) {
      return { port: document.getElementById('crPort').value.trim(),
        username: document.getElementById('crUser').value.trim(), auth: document.getElementById('crAuth').value,
        password: document.getElementById('crPass').value, private_key: document.getElementById('crKey').value,
        key_passphrase: document.getElementById('crKeyPass').value, note: document.getElementById('crNote').value };
    };
    var signature = function () { return JSON.stringify(devices.map(payload)); };
    var showResult = function (text,danger) { var host = document.getElementById('crResult'); if (host) host.innerHTML = notice(text,danger ? 'danger' : ''); };
    var buttons = function () { if (document.getElementById('crForm') !== form) return; test.disabled = busy; save.disabled = busy || testedSignature !== signature(); if (collect) collect.disabled = save.disabled; };
    var invalidate = function () { testedSignature = ''; buttons(); };
    var syncAuth = function () {
      var key = document.getElementById('crAuth').value === 'key';
      document.getElementById('crPasswordField').hidden = key;
      document.getElementById('crKeyFields').hidden = !key;
    };
    ['crPort','crUser','crAuth','crPass','crKey','crKeyPass','crNote'].forEach(function (id) {
      var node = document.getElementById(id); node.addEventListener('input',invalidate); node.addEventListener('change',invalidate);
    });
    document.getElementById('crAuth').addEventListener('change',syncAuth); syncAuth(); buttons();
    test.addEventListener('click', function () {
      if (busy) return;
      var p = payload(device);
      if (!p.port) { showResult('请手动输入 SSH 端口',true); document.getElementById('crPort').focus(); return; }
      if (!p.username) { showResult('请手动输入设备登录账号',true); document.getElementById('crUser').focus(); return; }
      if (p.auth === 'password' && !p.password) { showResult('请手动输入设备登录密码',true); document.getElementById('crPass').focus(); return; }
      if (p.auth === 'key' && !p.private_key && (multiple || !cred.has_secret || cred.auth !== 'key')) { showResult('请手动粘贴私钥内容',true); return; }
      if (devices.some(function (d) { var port = Number(payload(d).port); return !Number.isInteger(port) || port < 1 || port > 65535; })) { showResult('SSH 端口必须为 1～65535 的整数',true); return; }
      var sig = signature(); busy = true; testedSignature = ''; test.textContent = '测试中…'; buttons();
      Promise.all(devices.map(function (d) { return window.NetInspect.remoteTest(d.ip,payload(d)).then(function (res) {
        return {ip:d.ip,ok:!!res.ok,error:res.error || res.stage || '连接失败'};
      }).catch(function (err) { return {ip:d.ip,ok:false,error:err.message}; }); })).then(function (results) {
        if (document.getElementById('crForm') !== form) return;
        var failed = results.filter(function (r) { return !r.ok; });
        if (!failed.length && sig === signature()) { testedSignature = sig; showResult('连接测试通过（' + ips.length + ' 台），可以保存' + (onCollect ? '并采集' : '') + '。'); }
        else if (failed.length) showResult('连接测试失败：' + failed.map(function (r) { return r.ip + ' ' + r.error; }).join('；'),true);
        else showResult('输入已变化，请重新测试连接',true);
      }).finally(function () { busy = false; test.textContent = multiple ? '测试全部连接' : '测试连接'; buttons(); });
    });
    var saveCredentials = function (andCollect) {
      if (busy) return;
      if (!testedSignature || testedSignature !== signature()) { showResult('请先测试连接，全部通过后才能保存',true); return; }
      busy = true; buttons(); var payloads = devices.map(function (d) { return {ip:d.ip,body:payload(d)}; });
      var saved = 0, chain = Promise.resolve();
      payloads.forEach(function (item) { chain = chain.then(function () { return window.NetInspect.saveCredential(item.ip,item.body).then(function () { saved++; }); }); });
      chain.then(function () {
        ['crUser','crPass','crKey','crKeyPass'].forEach(function (id) { var node = document.getElementById(id); if (node) node.value = ''; });
        closeOverlay();
        if (andCollect && onCollect) { onCollect(); return; }
        showToast('已保存 ' + ips.length + ' 台设备凭据');
        if (autoConnect) { STATE.remote.ip = ip; var next = '#/console?category=' + encodeURIComponent(device.category || device.group_kind || 'switch') + '&device=' + encodeURIComponent(ip); if (location.hash === next) route(); else location.hash = next; }
        else route();
      }).catch(function (err) { showResult('保存失败：已保存 ' + saved + '/' + ips.length + ' 台。' + err.message,true); }).finally(function () { busy = false; if (document.getElementById('crForm') === form) buttons(); });
    };
    save.addEventListener('click',function () { saveCredentials(false); });
    if (collect) collect.addEventListener('click',function () { saveCredentials(true); });
    var reset = document.getElementById('crResetHostKey');
    if (reset) reset.addEventListener('click',function () { window.NetInspect.resetRemoteHostKey(ip).then(function () { invalidate(); showResult('主机指纹已清除，请重新测试连接'); }).catch(function (err) { showResult(err.message,true); }); });
    var del = document.getElementById('crDelete');
    if (del) del.addEventListener('click',function () { window.NetInspect.deleteCredential(ip).then(function () { closeOverlay(); route(); }).catch(function (err) { showResult(err.message,true); }); });
  }


  /* ---------- 命令策略弹窗 ---------- */
  function openPolicyModal() {
    var policy = STATE.remotePolicy || {};
    var inner =
      '<div class="modal" style="width:760px">' +
      '<div class="card-head" style="margin-bottom:14px"><div class="t">' +
      '<div class="title" style="font-size:18px">命令策略</div>' +
      '<div class="sub">按行写正则；硬拦截的命令不会收到回车，需确认的命令等操作员点「确认执行」</div></div>' +
      '<button class="icon-btn" id="plClose" style="width:32px;height:32px">' + icon('close', 16) + '</button></div>' +
      '<div class="form-row">' +
      field('模式', picker('plMode', [
        { value: 'confirm', label: '变更类命令需人工确认（推荐）' },
        { value: 'block', label: '只放行查看类命令（严格）' },
        { value: 'off', label: '不做命令拦截（仅留痕）' }
      ], policy.mode || 'confirm')) +
      field('登录后自动关分屏', picker('plPaging', [
        { value: '1', label: '开启（H3C/Huawei/Cisco 各自对应命令）' },
        { value: '0', label: '关闭' }
      ], policy.auto_disable_paging || '1')) +
      field('空闲断开（秒）', plainBox('plIdle', policy.idle_timeout_seconds || '600')) +
      field('单会话最长（分钟）', plainBox('plMax', policy.max_minutes || '120')) +
      '</div>' +
      '<div class="field"><label>禁止执行（破坏性，直接拦截）</label>' +
      '<div class="input" style="height:auto;padding:8px 12px"><textarea id="plBlock" rows="5" style="' + CTRL + ';resize:vertical;font-family:var(--font-mono);font-size:12px">' + esc(policy.block_patterns || '') + '</textarea></div></div>' +
      '<div class="field"><label>需要确认（变更类）</label>' +
      '<div class="input" style="height:auto;padding:8px 12px"><textarea id="plConfirm" rows="5" style="' + CTRL + ';resize:vertical;font-family:var(--font-mono);font-size:12px">' + esc(policy.confirm_patterns || '') + '</textarea></div></div>' +
      '<div class="form-row">' +
      field('试跑一条命令', plainBox('plSample', 'reboot')) +
      '<div class="field"><label>&nbsp;</label><button class="btn btn-ghost" id="plCheck">判定</button></div>' +
      '<div class="field" style="flex:2"><label>&nbsp;</label><div id="plCheckResult" class="kpi-trend">—</div></div>' +
      '</div>' +
      '<div class="footer-bar"><span class="kpi-trend">改动实时生效，无需重启</span>' +
      '<div class="btn-group"><button class="btn btn-ghost" id="plCancel">取消</button>' +
      '<button class="btn btn-primary" id="plSave">保存策略</button></div></div></div>';
    showOverlay(inner, false);
    var check = document.getElementById('plCheck');
    if (check) check.addEventListener('click', function () {
      var command = (document.getElementById('plSample') || {}).value || '';
      window.NetInspect.checkRemoteCommand(command).then(function (res) {
        document.getElementById('plCheckResult').innerHTML = tag(
          { ok: '放行', confirm: '需确认', block: '拦截' }[res.action] || res.action,
          res.action === 'ok' ? 'success' : res.action === 'block' ? 'danger' : 'warning') +
          ' <span class="mono">' + esc(res.reason || '') + '</span>';
      });
    });
    var save = document.getElementById('plSave');
    if (save) save.addEventListener('click', function () {
      window.NetInspect.saveRemotePolicy({
        mode: (document.getElementById('plMode') || {}).value,
        auto_disable_paging: (document.getElementById('plPaging') || {}).value,
        idle_timeout_seconds: (document.getElementById('plIdle') || {}).value,
        max_minutes: (document.getElementById('plMax') || {}).value,
        block_patterns: (document.getElementById('plBlock') || {}).value,
        confirm_patterns: (document.getElementById('plConfirm') || {}).value
      }).then(function (res) {
        STATE.remotePolicy = res.policy;
        showToast('命令策略已保存');
        closeOverlay();
        route();
      }).catch(function (err) { showToast('保存失败：' + err.message); });
    });
  }

  /* ---------- 会话记录（含命令留痕） ---------- */
  function openSessionModal(sessionId) {
    var session = ((STATE.remoteSessions || {}).sessions || []).filter(function (s) {
      return String(s.id) === String(sessionId);
    })[0] || {};
    window.NetInspect.remoteCommands(sessionId).then(function (res) {
      var inner =
        '<div class="drawer" style="width:680px">' +
        '<div class="card-head"><div class="t"><div class="title" style="font-size:18px">会话 #' + esc(sessionId) + ' 命令留痕</div>' +
        '<div class="sub">' + esc(session.device_name || session.device_ip || '') + ' · ' + esc(session.username || '') +
        ' · ' + esc(session.started_at || '') + ' → ' + esc(session.ended_at || '进行中') +
        ' · 命令 ' + (session.commands || 0) + ' · 拦截 ' + (session.blocked || 0) + '</div></div>' +
        '<button class="icon-btn" id="seClose" style="width:32px;height:32px">' + icon('close', 16) + '</button></div>' +
        '<div style="overflow-x:auto">' + ((res.commands || []).length ? table(
          [{ text: '时间', width: 150 }, { text: '命令', width: 320 }, { text: '动作', width: 90 }, { text: '说明' }],
          res.commands.map(function (c) {
            return [
              { text: c.created_at, cls: 'mono' },
              { text: c.command, cls: 'mono' },
              { html: tag(c.action === 'sent' ? '已下发' : (c.action === 'block' ? '已拦截' : '已取消'),
                c.action === 'sent' ? 'success' : (c.action === 'block' ? 'danger' : 'warning')) },
              { text: c.reason || '' }
            ];
          })) : emptyTable([{ text: '时间' }, { text: '命令' }, { text: '动作' }, { text: '说明' }], '这次会话没有记录到命令')) + '</div>' +
        '<div class="footer-bar"><span class="kpi-trend">会话与命令均落库留痕，可按时间追责</span>' +
        '<div class="btn-group"><button class="btn btn-ghost" id="seCancel">关闭</button></div></div></div>';
      showOverlay(inner, true);
    }).catch(function (err) { showToast('读取留痕失败：' + err.message); });
  }

  function openSftpModal(ip) {
    var device = (STATE.remoteDevices || []).filter(function (d) { return d.ip === ip; })[0] || {};
    var sftpState = { path: '', parent: '', entries: [] };
    var inner =
      '<div class="drawer" style="width:980px">' +
      '<div class="card-head"><div class="t"><div class="title" style="font-size:18px">SFTP 文件管理</div>' +
      '<div class="sub">' + esc(device.name || ip) + ' · ' + esc(ip) + ' · 与 SSH 终端共用同一套凭据和审计</div></div>' +
      '<button class="icon-btn" style="width:32px;height:32px" data-overlay-cancel>' + icon('close', 16) + '</button></div>' +
      '<div class="form-row">' +
      field('远端路径', plainBox('sftpPath', '')) +
      '<div class="field"><label>目录操作</label><div class="btn-group">' +
      '<button class="btn btn-primary sm" id="sftpGo">进入</button>' +
      '<button class="btn btn-ghost sm" id="sftpUp" disabled>上级目录</button>' +
      '<button class="btn btn-ghost sm" id="sftpRefresh">刷新</button>' +
      '<button class="btn btn-ghost sm" id="sftpMkdir">新建目录</button>' +
      '<button class="btn btn-primary sm" id="sftpUploadBtn">上传文件</button>' +
      '</div></div></div>' +
      '<input type="file" id="sftpFile" style="display:none"/>' +
      '<div id="sftpMeta" class="kpi-trend">正在读取目录…</div>' +
      '<div id="sftpList" style="overflow-x:auto;min-height:220px">' + loadingView('正在读取 SFTP 目录') + '</div>' +
      '<div class="footer-bar"><span class="kpi-trend">文件操作会写入操作审计；上传单文件上限 128MB</span>' +
      '<div class="btn-group"><button class="btn btn-ghost" data-overlay-cancel>关闭</button></div></div></div>';
    showOverlay(inner, true);

    var pathInput = document.getElementById('sftpPath');
    var listHost = document.getElementById('sftpList');
    var meta = document.getElementById('sftpMeta');
    var upBtn = document.getElementById('sftpUp');
    var fileInput = document.getElementById('sftpFile');

    function kindText(kind) { return kind === 'dir' ? '目录' : (kind === 'link' ? '链接' : '文件'); }
    function renderList(payload) {
      sftpState.path = payload.path || '';
      sftpState.parent = payload.parent || '';
      sftpState.entries = payload.entries || [];
      if (pathInput) pathInput.value = sftpState.path;
      if (upBtn) upBtn.disabled = !sftpState.parent;
      if (meta) meta.textContent = sftpState.path + ' · ' + sftpState.entries.length + ' 项';
      if (!sftpState.entries.length) {
        listHost.innerHTML = notice('当前目录为空');
        return;
      }
      var cols = [{ text: '名称', width: 300 }, { text: '类型', width: 80 },
        { text: '大小', width: 100 }, { text: '修改时间', width: 170 },
        { text: '权限', width: 90 }, { text: '操作', width: 210 }];
      var rows = sftpState.entries.map(function (item) {
        var action = item.kind === 'dir'
          ? '<a class="link" data-sftp-open="' + esc(item.path) + '" style="cursor:pointer">进入</a>'
          : '<a class="link" data-sftp-download="' + esc(item.path) + '" data-sftp-name="' + esc(item.name) + '" style="cursor:pointer">下载</a>';
        action += ' · <a class="link" data-sftp-rename="' + esc(item.path) + '" data-sftp-name="' + esc(item.name) + '" style="cursor:pointer">重命名</a>' +
          ' · <a class="danger-link" data-sftp-delete="' + esc(item.path) + '" data-sftp-name="' + esc(item.name) + '" style="cursor:pointer">删除</a>';
        return [
          { html: '<span class="strong">' + (item.kind === 'dir' ? '📁 ' : '📄 ') + esc(item.name) + '</span>' },
          { text: kindText(item.kind) },
          { text: item.kind === 'dir' ? '—' : (item.size_text || '—'), cls: 'mono' },
          { text: item.mtime || '—', cls: 'mono' },
          { text: item.mode || '—', cls: 'mono' },
          { html: action }
        ];
      });
      listHost.innerHTML = table(cols, rows);
      Array.prototype.forEach.call(listHost.querySelectorAll('[data-sftp-open]'), function (node) {
        node.addEventListener('click', function () { load(node.getAttribute('data-sftp-open')); });
      });
      Array.prototype.forEach.call(listHost.querySelectorAll('[data-sftp-download]'), function (node) {
        node.addEventListener('click', function () {
          download(window.NetInspect.remoteSftpDownloadUrl(ip, node.getAttribute('data-sftp-download')),
            { label: node.getAttribute('data-sftp-name') || 'SFTP 文件' });
        });
      });
      Array.prototype.forEach.call(listHost.querySelectorAll('[data-sftp-rename]'), function (node) {
        node.addEventListener('click', function () {
          var name = window.prompt('输入新名称', node.getAttribute('data-sftp-name') || '');
          if (!name) return;
          window.NetInspect.remoteSftpRename(ip, node.getAttribute('data-sftp-rename'), name)
            .then(function () { showToast('已重命名'); load(sftpState.path); })
            .catch(function (err) { showToast('重命名失败：' + err.message); });
        });
      });
      Array.prototype.forEach.call(listHost.querySelectorAll('[data-sftp-delete]'), function (node) {
        node.addEventListener('click', function () {
          window.NetInspect.remoteSftpDelete(ip, node.getAttribute('data-sftp-delete'))
            .then(function () { showToast('已删除'); load(sftpState.path); })
            .catch(function (err) { showToast('删除失败：' + err.message); });
        });
      });
    }

    function load(path) {
      listHost.innerHTML = loadingView('正在读取 SFTP 目录');
      window.NetInspect.remoteSftpList(ip, path || '').then(renderList).catch(function (err) {
        listHost.innerHTML = notice('SFTP 读取失败：' + err.message, 'danger');
        if (meta) meta.textContent = '读取失败';
      });
    }

    document.getElementById('sftpGo').addEventListener('click', function () { load(pathInput.value.trim()); });
    if (pathInput) pathInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); load(pathInput.value.trim()); }
    });
    if (upBtn) upBtn.addEventListener('click', function () { load(sftpState.parent); });
    document.getElementById('sftpRefresh').addEventListener('click', function () { load(sftpState.path); });
    document.getElementById('sftpMkdir').addEventListener('click', function () {
      var name = window.prompt('输入新目录名称');
      if (!name) return;
      window.NetInspect.remoteSftpMkdir(ip, sftpState.path || '.', name)
        .then(function () { showToast('目录已创建'); load(sftpState.path); })
        .catch(function (err) { showToast('新建失败：' + err.message); });
    });
    document.getElementById('sftpUploadBtn').addEventListener('click', function () { fileInput.click(); });
    fileInput.addEventListener('change', function () {
      var file = fileInput.files && fileInput.files[0];
      if (!file) return;
      if (file.size > 128 * 1024 * 1024) { showToast('单文件不能超过 128MB'); fileInput.value = ''; return; }
      showToast('正在上传 ' + file.name + '…');
      file.arrayBuffer().then(function (buffer) {
        return window.NetInspect.remoteSftpUpload(ip, sftpState.path || '.', file.name, buffer);
      }).then(function () {
        showToast('上传完成：' + file.name);
        fileInput.value = '';
        load(sftpState.path);
      }).catch(function (err) {
        fileInput.value = '';
        showToast('上传失败：' + err.message);
      });
    });
    load('');
  }
  function bindRemote(data) {
    var devices = data.devices || [];
    STATE.remoteDevices = devices;
    STATE.remotePolicy = data.policy || {};
    STATE.remoteSessions = data.sessions || {};
    STATE.blockedCommands = data.blocked_commands || 0;
    bindModuleTabs('remote-tab', function (tabKey) {
      if (STATE.remote.tab === 'terminal' && tabKey !== 'terminal') remoteDisconnect(true);
      STATE.remote.tab = tabKey;
      refreshPageHash('console', remoteQuery());
    });
    bindClientPager('rmDevices', STATE.remote, 'device_page', 'device_size', function () { refreshPageHash('console', remoteQuery()); });
    bindClientPager('rmSessionsPage', STATE.remote, 'session_page', 'session_size', function () { refreshPageHash('console', remoteQuery()); });
    Array.prototype.forEach.call(document.querySelectorAll('[data-go-console]'), function (node) {
      node.addEventListener('click', function () {
        STATE.remote.tab = 'terminal';
        refreshPageHash('console', remoteQuery());
      });
    });

    Array.prototype.forEach.call(document.querySelectorAll('[data-console-cat]'), function (node) {
      node.addEventListener('click', function () {
        var category = node.getAttribute('data-console-cat');
        if (!category || category === STATE.remote.category) return;
        STATE.remote.category = category;
        STATE.remote.ip = '';
        STATE.remote.device_page = 1;
        remoteDisconnect(true);
        refreshPageHash('console', remoteQuery());
      });
    });
    var sel = document.getElementById('rmDevice');
    if (sel) sel.addEventListener('change', function () {
      STATE.remote.ip = sel.value;
      STATE.remote.tab = 'terminal';
      refreshPageHash('console', remoteQuery());
    });
    var connect = document.getElementById('rmConnect');
    if (connect) connect.addEventListener('click', function () {
      var node = document.getElementById('rmDevice');
      remoteConnect(node ? node.value : '');
    });
    var disconnect = document.getElementById('rmDisconnect');
    if (disconnect) disconnect.addEventListener('click', function () { remoteDisconnect(false); });
    var sftp = document.getElementById('rmSftp');
    if (sftp) sftp.addEventListener('click', function () {
      var node = document.getElementById('rmDevice');
      var ip = node ? node.value : STATE.remote.ip;
      if (!ip) { showToast('请先选择设备'); return; }
      var device = devices.filter(function (d) { return d.ip === ip; })[0] || {};
      if (!(device.credential || {}).configured) {
        showToast('该设备还没有配置 SSH/SFTP 凭据');
        openCredentialModal(ip);
        return;
      }
      openSftpModal(ip);
    });
    var cred = document.getElementById('rmCred');
    if (cred) cred.addEventListener('click', function () {
      var node = document.getElementById('rmDevice');
      var ip = node ? node.value : STATE.remote.ip;
      if (!ip) { showToast('请先选择设备'); return; }
      openCredentialModal(ip);
    });
    var test = document.getElementById('rmTest');
    if (test) test.addEventListener('click', function () {
      var node = document.getElementById('rmDevice');
      var ip = node ? node.value : STATE.remote.ip;
      if (!ip) { showToast('请先选择设备'); return; }
      test.textContent = '测试中…';
      window.NetInspect.remoteTest(ip).then(function (res) {
        test.textContent = '测试连接';
        var hint = document.getElementById('rmHint');
        var text = res.ok
          ? ('测试通过：' + (res.username || '') + '，' + (res.elapsed_ms || 0) + ' ms，' + (res.ssh_version || ''))
          : ('测试失败（' + res.stage + '）：' + res.error);
        if (hint) hint.textContent = text;
        showToast(text);
      }).catch(function (err) {
        test.textContent = '测试连接';
        showToast('测试失败：' + err.message);
      });
    });
    var clear = document.getElementById('rmClear');
    if (clear) clear.addEventListener('click', function () { if (TERM.term) TERM.term.clear(); });
    var copy = document.getElementById('rmCopy');
    if (copy) copy.addEventListener('click', function () {
      var text = TERM.commands.map(function (c) { return c.created_at + '\t' + c.action + '\t' + c.command; }).join('\n');
      if (!text) { showToast('还没有命令记录'); return; }
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(function () { showToast('命令留痕已复制'); },
          function () { showToast('复制失败，浏览器未授权剪贴板'); });
      } else { showToast('当前浏览器不支持剪贴板接口'); }
    });
    var policy = document.getElementById('rmPolicy');
    if (policy) policy.addEventListener('click', openPolicyModal);
    var refresh = document.getElementById('rmRefresh');
    if (refresh) refresh.addEventListener('click', route);

    Array.prototype.forEach.call(document.querySelectorAll('[data-act]'), function (node) {
      node.addEventListener('click', function () {
        var ip = node.getAttribute('data-ip');
        var act = node.getAttribute('data-act');
        if (act === 'cred') { openCredentialModal(ip); return; }
        if (act === 'sftp') {
          var device = devices.filter(function (d) { return d.ip === ip; })[0] || {};
          if (!(device.credential || {}).configured) {
            showToast('该设备还没有配置 SSH/SFTP 凭据');
            openCredentialModal(ip);
          } else {
            openSftpModal(ip);
          }
          return;
        }
        if (act === 'test') {
          showToast('正在测试 ' + ip + ' …');
          window.NetInspect.remoteTest(ip).then(function (res) {
            showToast(res.ok ? (ip + ' 认证通过（' + (res.elapsed_ms || 0) + ' ms）')
                             : (ip + ' 测试失败（' + res.stage + '）：' + res.error));
          }).catch(function (err) { showToast(ip + ' 测试失败：' + err.message); });
          return;
        }
        var node2 = document.getElementById('rmDevice');
        if (node2) node2.value = ip;
        STATE.remote.ip = ip;
        if (STATE.remote.tab !== 'terminal') {
          STATE.remote.tab = 'terminal';
          refreshPageHash('console', remoteQuery());
          return;
        }
        remoteConnect(ip);
      });
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-session]'), function (node) {
      node.addEventListener('click', function () { openSessionModal(node.getAttribute('data-session')); });
    });

    // 仅在“终端会话”页签中自动连接，其他页签保持单内容展示
    if (!can('remote') || STATE.remote.tab !== 'terminal') return;
    if (STATE.remote.ip && (!TERM.connected || TERM.ip !== STATE.remote.ip)) {
      remoteConnect(STATE.remote.ip);
    }
    window.addEventListener('resize', termFit);
  }

  /* ---------- 页面：采集任务（自带采集 · 华为 VRP + Linux/Windows 服务器） ---------- */
  function pageCollect(data, sectionOnly, forcedTab) {
    var st = data || STATE.collect || {};
    var stats = (st.stats || {})['7d'] || {};
    var runs = st.runs || [];
    var logs = st.last_logs || [];
    var conf = st.settings || {};
    var cu = STATE.collectUi || (STATE.collectUi = {});
    var validTabs = ['devices', 'runs', 'logs', 'settings'];
    var tab = validTabs.indexOf(forcedTab) >= 0 ? forcedTab : (validTabs.indexOf(cu.tab) >= 0 ? cu.tab : 'devices');
    cu.tab = tab;
    var head =
      topbar('搜索设备 / 采集日志') +
      '<div class="page-head"><div class="page-title"><h1>设备采集中心</h1>' +
      '<div class="page-sub"><span>本平台自带采集（' + esc(st.vendor_label || '华为 VRP + 服务器') + '）· 只读命令 · ' +
      '设备 ' + esc(st.devices_total || 0) + ' 台 / 凭据就绪 ' + esc(st.credential_ready || 0) + ' 台</span>' +
      '<span>最近采集：' + esc(st.last_collect_at || '尚未采集') + '</span></div></div>' +
      '<div class="cta-row"><button class="btn btn-ghost" id="ctSettings">采集设置</button>' +
      '<button class="btn btn-ghost" id="ctPurge">清理历史</button></div></div>';

    var kpis = [
      { label: '台账设备', value: String(st.devices_total || 0), unit: '台', note: '本平台设备清单里的设备', tone: 'default' },
      { label: '凭据就绪', value: String(st.credential_ready || 0), unit: '台',
        note: st.credential_missing ? (st.credential_missing + ' 台还没配登录凭据') : '全部已配凭据',
        tone: st.credential_missing ? 'warning' : 'success' },
      { label: '近 7 天任务', value: String(stats.runs || 0), unit: '次', note: '成功 ' + (stats.ok || 0) + ' / 失败 ' + (stats.failed || 0) + ' 台次', tone: 'default' },
      { label: '采集成功率', value: (stats.success_rate === null || stats.success_rate === undefined) ? '—' : stats.success_rate + '%',
        unit: '', note: '覆盖 ' + (stats.devices || 0) + ' 台设备', tone: (stats.success_rate || 0) >= 95 ? 'success' : 'warning' }
    ];

    var allDevices = st.devices || [];
    var pf = STATE.collectPickFilter || { group: 'all', result: 'all' };
    var devices = allDevices.filter(function (d) {
      if (pf.group !== 'all' && (d.group || '') !== pf.group) return false;
      if (pf.result === 'ok' && d.last_ok !== true) return false;
      if (pf.result === 'failed' && d.last_ok !== false) return false;
      if (pf.result === 'never' && d.last_collect_at) return false;
      if (pf.result === 'ready' && !d.credential_ready) return false;
      return true;
    });
    var selected = STATE.collectSelected || {};
    var selectedCount = Object.keys(selected).filter(function (ip) { return selected[ip]; }).length;
    var canPick = function (d) { return !!d.credential_ready && d.supported !== false; };
    var readyCount = allDevices.filter(canPick).length;
    var groupOptions = [{ value: 'all', label: '全部分组' }].concat(
      Object.keys(allDevices.reduce(function (acc, d) { if (d.group) acc[d.group] = 1; return acc; }, {})).sort()
        .map(function (g) { return { value: g, label: g }; }));
    var resultOptions = [{ value: 'all', label: '全部结果' }, { value: 'failed', label: '上次失败' },
      { value: 'ok', label: '上次成功' }, { value: 'never', label: '从未采集' }, { value: 'ready', label: '已配凭据' }];
    var pre = STATE.collectPrecheck;
    var precheckPanel = pre ? ('<div class="module-inline-result">' + notice('连通性预检：' + pre.checked_at + ' · 可达 ' +
        pre.reachable + ' / 不可达 ' + pre.unreachable + '（TCP 探测，未登录设备）', pre.unreachable ? 'danger' : '') +
      '<div style="max-height:180px;overflow:auto;margin-top:8px">' + table(
        [{ text: '设备', width: 160 }, { text: 'IP:端口', width: 160 }, { text: '结果', width: 90 }, { text: '耗时', width: 90 }, { text: '说明' }],
        pre.results.map(function (x) {
          return [{ text: x.name, cls: 'strong' }, { text: x.ip + ':' + x.port, cls: 'mono' },
                  { html: x.reachable ? tag('可达', 'success') : tag('不可达', 'danger') },
                  { text: x.latency_ms + ' ms', cls: 'mono' }, { text: x.error || '' }];
        })) + '</div>' +
      (pre.unreachable ? '<div class="btn-group" style="justify-content:flex-end;margin-top:8px">' +
        '<button class="btn btn-ghost sm" id="ctDropUnreachable">取消勾选不可达的 ' + pre.unreachable + ' 台</button></div>' : '') +
      '</div>') : '';

    var deviceView = clientPage(devices, cu, 'device_page', 'device_size', [10, 20, 50], 10);
    var devRows = deviceView.rows.map(function (d) {
      var checked = !!selected[d.ip];
      var last = d.last_collect_at ? (esc(d.last_collect_at) + ' · ' + (d.last_ok ? '成功' : '失败')) : '尚未采集';
      return [
        { html: '<input type="checkbox" data-pick="' + esc(d.ip) + '"' + (checked ? ' checked' : '') +
            (canPick(d) ? '' : ' disabled') + ' style="width:15px;height:15px;cursor:pointer"/>' },
        { text: d.name, cls: 'strong' }, { text: d.ip, cls: 'mono' }, { text: d.type_label || '—' },
        { text: d.group || '—' },
        { html: (d.online ? tag('在线', 'success') : tag('离线', 'danger')) + ' ' +
            (d.credential_ready ? tag('已配凭据', 'success') : tag('缺凭据', 'warning')) +
            (d.supported === false ? ' ' + tag('不支持采集·仅远程登录', 'neutral') : '') },
        { text: last, cls: 'mono dim' }, { text: (d.last_result || '').slice(0, 40) },
        { html: d.supported === false
            ? '<a class="link" data-pickremote="' + esc(d.ip) + '" style="cursor:pointer">远程登录</a>'
            : (d.credential_ready ? '<span class="kpi-trend">勾选后统一采集</span>'
                : '<a class="link" data-pickcred="' + esc(d.ip) + '" style="cursor:pointer">补凭据</a>') }
      ];
    });
    var devCols = [{ text: '', width: 42 }, { text: '设备名称', width: 150 }, { text: 'IP 地址', width: 120 },
      { text: '类型', width: 100 }, { text: '分组', width: 100 }, { text: '凭据', width: 110 },
      { text: '最近采集', width: 190 }, { text: '上次结果' }, { text: '操作', width: 90 }];
    var devicesCard = '<div class="card tight overview-module-card">' +
      cardHead('选择设备采集', '勾选要采的几台；交换机走华为 VRP，服务器走 SSH（Linux / Windows OpenSSH）',
        '<span class="kpi-trend" id="pickCount">已选 ' + selectedCount + ' / 可采 ' + readyCount + ' 台</span>') +
      '<div class="form-row module-filter-row">' + field('分组', picker('ctPickGroup', groupOptions, pf.group)) +
      field('上次结果', picker('ctPickResult', resultOptions, pf.result)) +
      '<div class="field"><label>&nbsp;</label><span class="kpi-trend">筛选出 ' + devices.length + ' / ' + allDevices.length + ' 台</span></div></div>' +
      '<div class="btn-group module-action-row">' +
      '<button class="btn btn-ghost sm" id="ctPickAll">勾选筛选结果（' + devices.filter(canPick).length + '）</button>' +
      '<button class="btn btn-ghost sm" id="ctPickNone">取消勾选</button>' +
      '<button class="btn btn-ghost sm" id="ctPrecheck">连通性预检</button>' +
      '<button class="btn btn-ghost sm" id="ctAll">全选可采设备</button>' +
      '<button class="btn btn-ghost sm" id="ctInvert">反选</button>' +
      '<button class="btn btn-ghost sm" id="ctClear">清空选择</button>' +
      '<label class="radio" style="font-size:13px;color:var(--text-2)"><input id="ctWithConfig" type="checkbox"' +
      (STATE.collectWithConfig ? ' checked' : '') + ' style="width:14px;height:14px"/> 同时抓配置备份</label>' +
      '<button class="btn btn-primary sm" id="ctRunPicked"' + (selectedCount ? '' : ' disabled') + '>' +
      icon('refresh', 14) + '采集选中的 ' + selectedCount + ' 台</button></div>' + precheckPanel +
      '<div style="overflow-x:auto">' + (devRows.length ? table(devCols, devRows)
        : emptyTable(devCols, '没有符合条件的设备（换个筛选条件，或去设备清单新增交换机 / 服务器）')) + '</div>' +
      pagerFooter('ctDev', deviceView, '台') + '</div>';

    var runView = clientPage(runs, cu, 'runs_page', 'runs_size', [10, 20, 50], 10);
    var runRows = runView.rows.map(function (run) {
      return [
        { text: '#' + run.id, cls: 'dim mono' }, { text: run.started_at, cls: 'mono' },
        { text: run.trigger === 'schedule' ? '定时' : '手动' }, { text: (run.total || 0) + ' 台', cls: 'mono' },
        { html: '<span class="status-text success">' + (run.ok || 0) + '</span> / <span class="status-text ' +
            ((run.failed || 0) ? 'danger' : 'muted') + '">' + (run.failed || 0) + '</span>' },
        { text: ((run.duration_ms || 0) / 1000).toFixed(1) + ' s', cls: 'mono' }, { text: run.message || '' },
        { html: '<a class="link" data-runlogs="' + run.id + '" style="cursor:pointer">看日志</a>' }
      ];
    });
    var runCols = [{ text: '任务', width: 70 }, { text: '开始时间', width: 160 }, { text: '触发', width: 70 },
      { text: '范围', width: 80 }, { text: '成功 / 失败', width: 110 }, { text: '耗时', width: 90 },
      { text: '结果', width: 220 }, { text: '操作', width: 80 }];
    var runsCard = '<div class="card tight overview-module-card">' +
      cardHead('采集任务历史', '共 ' + runs.length + ' 次' + (st.running ? ' · 正在采集…' : ''), '') +
      '<div style="overflow-x:auto">' + (runRows.length ? table(runCols, runRows)
        : emptyTable(runCols, '还没有采集任务：在待采集列表勾选设备后点击「采集选中」')) + '</div>' +
      pagerFooter('ctRunHis', runView, '次') + '</div>';

    var logView = clientPage(logs, cu, 'logs_page', 'logs_size', [10, 20, 50], 20);
    var logRows = logView.rows.map(function (log) {
      return [
        { text: log.created_at, cls: 'mono' }, { text: log.device_name || log.device_ip, cls: 'strong' },
        { text: log.device_ip, cls: 'mono' }, { html: log.ok ? tag('成功', 'success') : tag('失败', 'danger') },
        { text: ((log.duration_ms || 0) / 1000).toFixed(1) + ' s', cls: 'mono' },
        { text: log.ok ? (log.summary || '') : (log.reason || '') },
        { html: '<a class="link" data-log="' + log.id + '" style="cursor:pointer">看回显</a>' }
      ];
    });
    var logCols = [{ text: '时间', width: 150 }, { text: '设备', width: 150 }, { text: 'IP', width: 120 },
      { text: '结果', width: 80 }, { text: '耗时', width: 80 }, { text: '摘要 / 失败原因' }, { text: '回显', width: 80 }];
    var logFilter = '<div class="form-row module-filter-row">' +
      field('设备', picker('ctDevice', [{ value: '', label: '全部设备' }].concat(
        (STATE.collectDevices || []).map(function (d) { return { value: d.ip, label: d.name + '（' + d.ip + '）' }; })),
        STATE.collectFilter.ip)) +
      field('只看', picker('ctOnly', [{ value: '0', label: '全部结果' }, { value: '1', label: '只看失败' }],
        STATE.collectFilter.only_failed ? '1' : '0')) +
      '<div class="field"><label>&nbsp;</label><div class="btn-group">' +
      '<button class="btn btn-primary sm" id="ctQuery">查询</button>' +
      '<button class="btn btn-ghost sm" id="ctExportLogs">导出日志 CSV</button></div></div></div>';
    var logsCard = '<div class="card tight overview-module-card">' +
      cardHead('采集日志', '列表不含原始回显，点「看回显」查看单台明细', '') + logFilter +
      '<div style="overflow-x:auto">' + (logRows.length ? table(logCols, logRows)
        : emptyTable(logCols, '所选条件下没有采集日志')) + '</div>' +
      pagerFooter('ctLogs', logView, '条') + '</div>';

    var changes = st.change_alerts || [];
    var changeView = clientPage(changes, cu, 'changes_page', 'changes_size', [10, 20, 50], 10);
    var changesCard = '<div class="card tight overview-module-card">' +
      cardHead('采集结果变化提醒', '跟该设备上一轮采集对比 · 最近 ' + changes.length + ' 条', '') +
      (changeView.rows.length ? '<div class="stat-list">' + changeView.rows.map(function (c) {
        return '<div class="stat-item"><span class="n" style="white-space:normal">' + esc(c.title) + '</span>' +
          '<span class="v">' + esc(c.device) + (c.device_ip ? '（' + esc(c.device_ip) + '）' : '') + ' · ' + esc(c.time) + '</span>' +
          '<span style="margin-left:auto">' + tag(c.label || '变化', c.severity === 'critical' ? 'danger' : 'warning') + '</span></div>';
      }).join('') + '</div>' : notice('最近一轮采集没有检测到需要提醒的变化')) +
      pagerFooter('ctChanges', changeView, '条') + '</div>';

    var missing = st.missing_devices || [];
    var missingView = clientPage(missing, cu, 'missing_page', 'missing_size', [10, 20, 50], 10);
    var settingsCard = '<div class="card overview-module-card">' + cardHead('采集设置', '改动即时生效，不用重启',
        tag(str(conf.enabled) === '1' ? '定时开启' : '定时关闭', str(conf.enabled) === '1' ? 'success' : 'neutral')) +
      statList([
        { name: '定时采集', value: String(conf.enabled) === '1' ? '开启' : '关闭' },
        { name: '采集周期', value: (conf.interval_minutes || '60') + ' 分钟' },
        { name: '并发台数', value: (conf.concurrency || '5') + ' 台' },
        { name: '单台超时', value: (conf.timeout || '25') + ' 秒' },
        { name: '抓配置备份', value: String(conf.with_config) === '1' ? '是' : '否' },
        { name: '告警去重窗口', value: (conf.alert_cooldown_hours || '24') + ' 小时' },
        { name: '变化检测提醒', value: String(conf.alert_on_change) === '1'
            ? ('开启（CPU +' + (conf.cpu_delta || '30') + ' / 内存 +' + (conf.mem_delta || '25') + ' / 错包 +' + (conf.err_delta || '100') + '）') : '关闭' },
        { name: '持续高位提醒', value: '连续 ' + (conf.high_streak || '3') + ' 次 ≥ ' + (conf.high_pct || '80') + '%' }
      ]) + '<div class="footer-bar"><span class="kpi-trend">定时任务与手动采集共用一把锁</span>' +
      '<button class="btn btn-ghost sm" id="ctSettings2">修改设置</button></div></div>';

    var commandsCard = '<div class="card overview-module-card">' + cardHead('将执行的命令', '全部为只读 display 命令', '') +
      '<div class="stat-list">' + (st.commands || []).map(function (cmd) {
        return '<div class="stat-item"><span class="n mono" style="font-size:12px">' + esc(cmd) + '</span></div>';
      }).join('') + '</div>' +
      '<div class="footer-bar"><span class="kpi-trend">不会修改设备配置，不做重启、保存或删除操作</span></div></div>';

    var missingCard = '<div class="card tight overview-module-card">' +
      cardHead('还没配凭据的设备', missing.length + ' 台', '') +
      (missing.length ? '<div class="stat-list module-device-list">' + missingView.rows.map(function (d) {
        return '<div class="stat-item" data-godev="' + esc(d.ip) + '" style="cursor:pointer"><span class="n">' + esc(d.name) +
          '</span><span class="v mono">' + esc(d.ip) + '</span></div>';
      }).join('') + '</div><div class="kpi-trend" style="margin-top:8px">去设备清单点「凭据」补账号口令</div>'
        : notice('台账里的设备都已配好凭据')) + pagerFooter('ctMissing', missingView, '台') + '</div>';

    var tabs = moduleTabs([
      { key: 'devices', label: '采集设备', icon: 'refresh', count: devices.length },
      { key: 'runs', label: '任务历史', icon: 'archive', count: runs.length },
      { key: 'logs', label: '采集日志', icon: 'file', count: logs.length },
      { key: 'settings', label: '采集设置', icon: 'settings' }
    ], tab, 'collect-tab', '<span>采集任务、日志与设置可独立切换</span>');
    var body = tab === 'runs' ? runsCard : tab === 'logs' ? logsCard : tab === 'settings' ? settingsCard : devicesCard;
    if (sectionOnly) return body;
    return head + kpiCards(kpis, true) + tabs + body;
  }

  function str(v) { return v === undefined || v === null ? '' : String(v); }

  /** 勾选状态就地更新（不整页重绘，避免连点丢选择） */
  function updatePickSummary() {
    var sel = STATE.collectSelected || {};
    var chosen = Object.keys(sel).filter(function (ip) { return sel[ip]; });
    var devices = (STATE.collect || {}).devices || [];
    var ready = devices.filter(function (d) { return d.credential_ready && d.supported !== false; }).length;
    var chip = document.getElementById('pickCount');
    if (chip) chip.textContent = '已选 ' + chosen.length + ' / 可采 ' + ready + ' 台';
    var btn = document.getElementById('ctRunPicked');
    if (btn) {
      btn.disabled = !chosen.length;
      btn.innerHTML = icon('refresh', 14) + '采集选中的 ' + chosen.length + ' 台';
    }
  }

  

  function openLogDetail(logId) {
    window.NetInspect.collectLog(logId).then(function (log) {
      var inner =
        '<div class="drawer" style="width:820px">' +
        '<div class="card-head"><div class="t"><div class="title" style="font-size:18px">采集明细 · ' +
        esc(log.device_name || log.device_ip) + '</div>' +
        '<div class="sub">' + esc(log.created_at) + ' · ' + (log.ok ? '成功' : '失败') +
        ' · 耗时 ' + ((log.duration_ms || 0) / 1000).toFixed(1) + ' s · 任务 #' + esc(log.run_id) + '</div></div>' +
        '<button class="icon-btn" id="ldClose" style="width:32px;height:32px">' + icon('close', 16) + '</button></div>' +
        (log.ok ? notice(log.summary || '') : notice(log.reason || '采集失败', 'danger')) +
        '<div style="font-size:12px;color:var(--text-3);margin-top:8px">执行过的命令</div>' +
        '<div class="input" style="height:auto;padding:10px 12px;font-family:var(--font-mono);font-size:12px">' +
        esc(log.commands || '—') + '</div>' +
        '<div style="font-size:12px;color:var(--text-3);margin-top:10px">原始回显摘要（裁剪留存，用于排错）</div>' +
        '<div class="input" style="height:auto;padding:10px 12px;max-height:380px;overflow:auto;' +
        'font-family:var(--font-mono);font-size:12px;white-space:pre-wrap">' +
        esc(log.raw_excerpt || '（本次没有留存回显，失败设备通常没有回显）') + '</div>' +
        '<div class="footer-bar"><span class="kpi-trend">采集只执行 display 类只读命令</span>' +
        '<div class="btn-group"><button class="btn btn-ghost" id="ldCancel">关闭</button></div></div></div>';
      showOverlay(inner, true);
    }).catch(function (err) { showToast('读取采集明细失败：' + err.message); });
  }

  function openCollectSettings() {
    var conf = (STATE.collect || {}).settings || {};
    var inner =
      '<div class="modal" style="width:700px">' +
      '<div class="card-head" style="margin-bottom:14px"><div class="t">' +
      '<div class="title" style="font-size:18px">采集设置</div>' +
      '<div class="sub">本平台自带采集（华为 VRP 交换机 + Linux/Windows 服务器）；改动即时生效，定时任务与手动采集共用一把锁</div></div>' +
      '<button class="icon-btn" id="csClose" style="width:32px;height:32px">' + icon('close', 16) + '</button></div>' +
      '<div class="form-row">' +
      field('定时采集', picker('csEnabled', [{ value: '1', label: '开启' }, { value: '0', label: '关闭' }], str(conf.enabled) || '1')) +
      field('采集周期（分钟）', plainBox('csInterval', str(conf.interval_minutes || '60'))) +
      field('并发台数', plainBox('csConcurrency', str(conf.concurrency || '5'))) +
      '</div>' +
      '<div class="form-row">' +
      field('单台超时（秒）', plainBox('csTimeout', str(conf.timeout || '25'))) +
      field('同时抓配置备份', picker('csWithConfig', [{ value: '0', label: '不抓（更快）' },
        { value: '1', label: '抓 display current-configuration' }], str(conf.with_config) || '0')) +
      field('同类告警去重窗口（小时）', plainBox('csCooldown', str(conf.alert_cooldown_hours || '24'))) +
      '</div>' +
      '<div class="form-row">' +
      field('变化检测提醒', picker('csOnChange', [{ value: '1', label: '开启（推荐）' },
        { value: '0', label: '关闭' }], str(conf.alert_on_change) || '1')) +
      field('CPU 突增阈值（百分点）', plainBox('csCpuDelta', str(conf.cpu_delta || '30'))) +
      field('内存突增阈值（百分点）', plainBox('csMemDelta', str(conf.mem_delta || '25'))) +
      '</div>' +
      '<div class="form-row">' +
      field('错包增长阈值（个）', plainBox('csErrDelta', str(conf.err_delta || '100'))) +
      field('持续高位阈值（%）', plainBox('csHighPct', str(conf.high_pct || '80'))) +
      field('连续高位次数', plainBox('csHighStreak', str(conf.high_streak || '3'))) +
      '</div>' +
      '<div class="form-row">' +
      field('服务器备份目录（Linux，留空 = /var/backups）', plainBox('csServerBakLinux', str(conf.server_backup_path_linux || ''))) +
      field('服务器备份目录（Windows，留空 = C:\\Backup）', plainBox('csServerBakWin', str(conf.server_backup_path_windows || ''))) +
      '</div>' +
      '<div class="kpi-trend" style="margin:-6px 0 10px">变化检测＝把这一轮采集跟该设备「上一轮」比：CPU/内存突增、端口新变 down 或恢复、' +
      '错包快速增长、STP 被禁用、设备重启（运行时长变小）都会写成告警；「持续高位」按最近 N 次是否都超阈值提醒。</div>' +
      '<div id="csResult"></div>' +
      '<div class="footer-bar"><span class="kpi-trend">平台需要能 SSH 到设备（交换机 VRP / 服务器 Linux、Windows OpenSSH；端口按设备台账里的设置）</span>' +
      '<div class="btn-group"><button class="btn btn-ghost" id="csCancel">取消</button>' +
      '<button class="btn btn-primary" id="csSave">保存设置</button></div></div></div>';
    showOverlay(inner, false);
    var save = document.getElementById('csSave');
    if (save) save.addEventListener('click', function () {
      save.textContent = '保存中…';
      window.NetInspect.saveCollectSettings({
        enabled: (document.getElementById('csEnabled') || {}).value,
        interval_minutes: (document.getElementById('csInterval') || {}).value,
        concurrency: (document.getElementById('csConcurrency') || {}).value,
        timeout: (document.getElementById('csTimeout') || {}).value,
        with_config: (document.getElementById('csWithConfig') || {}).value,
        alert_cooldown_hours: (document.getElementById('csCooldown') || {}).value,
        alert_on_change: (document.getElementById('csOnChange') || {}).value,
        cpu_delta: (document.getElementById('csCpuDelta') || {}).value,
        mem_delta: (document.getElementById('csMemDelta') || {}).value,
        err_delta: (document.getElementById('csErrDelta') || {}).value,
        high_pct: (document.getElementById('csHighPct') || {}).value,
        high_streak: (document.getElementById('csHighStreak') || {}).value,
        server_backup_path_linux: (document.getElementById('csServerBakLinux') || {}).value,
        server_backup_path_windows: (document.getElementById('csServerBakWin') || {}).value
      }).then(function () {
        closeOverlay();
        showToast('采集设置已保存');
        route();
      }).catch(function (err) {
        save.textContent = '保存设置';
        document.getElementById('csResult').innerHTML = notice(err.message, 'danger');
      });
    });
  }

  function bindCollect(data, embedded) {
    STATE.collect = data;
    STATE.collectDevices = data.devices || [];
    if (!STATE.collectFilter) STATE.collectFilter = { ip: '', only_failed: 0, limit: 500, run_id: 0 };
    if (!STATE.collectUi) STATE.collectUi = { tab: 'devices', device_page: 1, device_size: 10, runs_page: 1, runs_size: 10,
      logs_page: 1, logs_size: 20, changes_page: 1, changes_size: 10, missing_page: 1, missing_size: 10 };
    var refreshCollect = function () { refreshPageHash('pending', pendingQuery()); };
    if (!embedded) {
      bindModuleTabs('collect-tab', function (tabKey) {
        STATE.collectUi.tab = tabKey;
        refreshCollect();
      });
    }
    bindClientPager('ctDev', STATE.collectUi, 'device_page', 'device_size', refreshCollect);
    bindClientPager('ctRunHis', STATE.collectUi, 'runs_page', 'runs_size', refreshCollect);
    bindClientPager('ctLogs', STATE.collectUi, 'logs_page', 'logs_size', refreshCollect);

    var pickedRun = document.getElementById('ctRunPicked');
    if (pickedRun) pickedRun.addEventListener('click', function () {
      var ips = Object.keys(STATE.collectSelected).filter(function (ip) { return STATE.collectSelected[ip]; });
      if (!ips.length) { showToast('先勾选要采集的设备'); return; }
      runPendingCollection(ips, !!(document.getElementById('ctWithConfig') || {}).checked);
    });
    var cfgBox = document.getElementById('ctWithConfig');
    if (cfgBox) cfgBox.addEventListener('change', function () { STATE.collectWithConfig = cfgBox.checked; });
    var setAll = function (mode) {
      var devices = (STATE.collect || {}).devices || [];
      devices.forEach(function (d) {
        if (!d.credential_ready || d.supported === false) return;
        if (mode === 'all') STATE.collectSelected[d.ip] = true;
        if (mode === 'none') STATE.collectSelected[d.ip] = false;
        if (mode === 'invert') STATE.collectSelected[d.ip] = !STATE.collectSelected[d.ip];
      });
      Array.prototype.forEach.call(document.querySelectorAll('[data-pick]'), function (box) {
        box.checked = !!STATE.collectSelected[box.getAttribute('data-pick')];
      });
      updatePickSummary();
    };
    var groupSel = document.getElementById('ctPickGroup');
    if (groupSel) groupSel.addEventListener('change', function () {
      STATE.collectPickFilter.group = groupSel.value;
      STATE.collectUi.device_page = 1;
      refreshPageHash('pending', pendingQuery());
    });
    var resultSel = document.getElementById('ctPickResult');
    if (resultSel) resultSel.addEventListener('change', function () {
      STATE.collectPickFilter.result = resultSel.value;
      STATE.collectUi.device_page = 1;
      refreshPageHash('pending', pendingQuery());
    });
    var pickAll = document.getElementById('ctPickAll');
    if (pickAll) pickAll.addEventListener('click', function () {
      var pf = STATE.collectPickFilter || {};
      ((STATE.collect || {}).devices || []).forEach(function (d) {
        if (!d.credential_ready || d.supported === false) return;
        if (pf.group !== 'all' && (d.group || '') !== pf.group) return;
        if (pf.result === 'ok' && d.last_ok !== true) return;
        if (pf.result === 'failed' && d.last_ok !== false) return;
        if (pf.result === 'never' && d.last_collect_at) return;
        if (pf.result === 'ready' && !d.credential_ready) return;
        STATE.collectSelected[d.ip] = true;
      });
      route();
    });
    var pickNone = document.getElementById('ctPickNone');
    if (pickNone) pickNone.addEventListener('click', function () {
      var pf = STATE.collectPickFilter || {};
      ((STATE.collect || {}).devices || []).forEach(function (d) {
        if (pf.group !== 'all' && (d.group || '') !== pf.group) return;
        if (pf.result === 'ok' && d.last_ok !== true) return;
        if (pf.result === 'failed' && d.last_ok !== false) return;
        if (pf.result === 'never' && d.last_collect_at) return;
        if (pf.result === 'ready' && !d.credential_ready) return;
        STATE.collectSelected[d.ip] = false;
      });
      route();
    });
    var preBtn = document.getElementById('ctPrecheck');
    if (preBtn) preBtn.addEventListener('click', function () {
      var ips = Object.keys(STATE.collectSelected).filter(function (ip) { return STATE.collectSelected[ip]; });
      preBtn.textContent = '预检中…';
      window.NetInspect.collectPrecheck(ips.length ? ips : null).then(function (res) {
        STATE.collectPrecheck = res;
        showToast('预检完成：可达 ' + res.reachable + ' / 不可达 ' + res.unreachable);
        route();
      }).catch(function (err) {
        preBtn.textContent = '连通性预检';
        showToast('预检失败：' + err.message);
      });
    });
    var dropBtn = document.getElementById('ctDropUnreachable');
    if (dropBtn) dropBtn.addEventListener('click', function () {
      ((STATE.collectPrecheck || {}).results || []).forEach(function (x) {
        if (!x.reachable) STATE.collectSelected[x.ip] = false;
      });
      showToast('已取消勾选不可达的设备');
      route();
    });
    var expLogs = document.getElementById('ctExportLogs');
    if (expLogs) expLogs.addEventListener('click', function () {
      var f = STATE.collectFilter || {};
      download(window.NetInspect.collectLogsCsvUrl({
        ip: f.ip || '', only_failed: f.only_failed ? 1 : 0, run_id: f.run_id || 0, limit: 1000
      }), { label: '采集日志', ext: 'csv' });
    });
    var allBtn = document.getElementById('ctAll');
    if (allBtn) allBtn.addEventListener('click', function () { setAll('all'); });
    var invBtn = document.getElementById('ctInvert');
    if (invBtn) invBtn.addEventListener('click', function () { setAll('invert'); });
    var clearBtn = document.getElementById('ctClear');
    if (clearBtn) clearBtn.addEventListener('click', function () { setAll('none'); });
    Array.prototype.forEach.call(document.querySelectorAll('[data-pick]'), function (box) {
      box.addEventListener('change', function () {
        STATE.collectSelected[box.getAttribute('data-pick')] = box.checked;
        updatePickSummary();
      });
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-pickcred]'), function (link) {
      link.addEventListener('click', function () {
        STATE.remoteDevices = STATE.collectDevices || [];
        openCredentialModal(link.getAttribute('data-pickcred'));
      });
    });
    // 非华为设备：采集不了，直接带去「远程登录」控制台
    Array.prototype.forEach.call(document.querySelectorAll('[data-pickremote]'), function (link) {
      link.addEventListener('click', function () {
        STATE.remote.ip = link.getAttribute('data-pickremote');
        location.hash = '#/console?device=' + encodeURIComponent(STATE.remote.ip);
      });
    });
    ['ctSettings', 'ctSettings2'].forEach(function (id) {
      var btn = document.getElementById(id);
      if (btn) btn.addEventListener('click', openCollectSettings);
    });
    var purge = document.getElementById('ctPurge');
    if (purge) purge.addEventListener('click', function () {
      window.NetInspect.collectPurge(30).then(function (res) {
        showToast('已清理 ' + res.removed + ' 条历史日志');
        route();
      }).catch(function (err) { showToast('清理失败：' + err.message); });
    });
    var query = document.getElementById('ctQuery');
    if (query) query.addEventListener('click', function () {
      STATE.collectFilter.ip = (document.getElementById('ctDevice') || {}).value || '';
      STATE.collectFilter.only_failed = (document.getElementById('ctOnly') || {}).value === '1';
      STATE.collectFilter.limit = 500;
      STATE.collectUi.logs_page = 1;
      refreshPageHash('pending', pendingQuery());
    });
    var deviceSel = document.getElementById('ctDevice');
    if (deviceSel) deviceSel.addEventListener('change', function () {
      STATE.collectFilter.ip = deviceSel.value;
      STATE.collectFilter.only_failed = (document.getElementById('ctOnly') || {}).value === '1';
      STATE.collectUi.logs_page = 1;
      refreshPageHash('pending', pendingQuery());
    });
    var onlySel = document.getElementById('ctOnly');
    if (onlySel) onlySel.addEventListener('change', function () {
      STATE.collectFilter.only_failed = onlySel.value === '1';
      STATE.collectFilter.ip = (document.getElementById('ctDevice') || {}).value || '';
      STATE.collectUi.logs_page = 1;
      refreshPageHash('pending', pendingQuery());
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-log]'), function (node) {
      node.addEventListener('click', function () { openLogDetail(node.getAttribute('data-log')); });
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-runlogs]'), function (node) {
      node.addEventListener('click', function () {
        STATE.collectFilter.run_id = Number(node.getAttribute('data-runlogs'));
        STATE.collectFilter.ip = '';
        STATE.collectFilter.only_failed = false;
        STATE.pending.tab = 'logs';
        STATE.collectUi.tab = 'logs';
        STATE.collectUi.logs_page = 1;
        refreshPageHash('pending', pendingQuery());
      });
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-godev]'), function (node) {
      node.addEventListener('click', function () {
        STATE.devices.keyword = node.getAttribute('data-godev');
        STATE.devices.page = 1;
        location.hash = '#/devices?keyword=' + encodeURIComponent(node.getAttribute('data-godev'));
      });
    });
  }

  /* ---------- 页面：大屏轮播（巡检总览 · 每台设备） ---------- */
  function wallNum(value, unit) {
    if (value === null || value === undefined || value === '') return '—';
    var num = Number(value);
    if (isNaN(num)) return '—';
    return (num % 1 === 0 ? String(num) : num.toFixed(1)) + (unit || '');
  }

  function wallPct(value) {
    if (value === null || value === undefined || value === '') return null;
    var num = Number(value);
    return isNaN(num) ? null : Math.max(0, Math.min(100, num));
  }

  

  function wallScoreTone(score) {
    if (score === null || score === undefined) return '#64748b';
    if (score >= 95) return '#22c55e';
    if (score >= 85) return '#f59e0b';
    return '#ef4444';
  }

  

  

  var WALL_CHART_SEQ = 0;

  function wallSeriesColor(kind, metric) {
    var map = {
      switch: { health: '#22c55e', cpu: '#38bdf8', memory: '#2dd4bf' },
      server: { health: '#34d399', cpu: '#a78bfa', memory: '#60a5fa' },
      security: { health: '#4ade80', cpu: '#f59e0b', memory: '#fb7185' }
    };
    return (map[kind] || map.switch)[metric];
  }

  function wallTrendChart(item, kind) {
    var trend = item.trend || {};
    var labels = trend.labels || [];
    var healthValues = trend.health || [];
    var cpuValues = trend.cpu || [];
    var memoryValues = trend.memory || [];
    var hasValue = healthValues.concat(cpuValues, memoryValues).some(function (v) {
      return v !== null && v !== undefined && !isNaN(Number(v));
    });
    if (!labels.length || !hasValue) {
      return '<div class="wall-chart-card"><div class="wall-chart-empty">' +
        icon('refresh', 16) + '<span>等待下一次采集形成实时曲线</span></div></div>';
    }
    var W = 800, H = 130, PL = 8, PR = 8, PT = 10, PB = 8;
    var pw = W - PL - PR, ph = H - PT - PB;
    var count = labels.length;
    var step = count > 1 ? pw / (count - 1) : 0;
    var xAt = function (i) { return count > 1 ? PL + i * step : PL + pw / 2; };
    var yAt = function (v) { return PT + (100 - Math.max(0, Math.min(100, Number(v)))) / 100 * ph; };
    var grid = [0, 25, 50, 75, 100].map(function (v) {
      var y = yAt(v);
      return '<line class="wall-grid-line" x1="' + PL + '" y1="' + y + '" x2="' + (W - PR) + '" y2="' + y + '"></line>';
    }).join('');
    function series(values, color, label) {
      var pts = [];
      values.forEach(function (v, i) {
        if (v !== null && v !== undefined && !isNaN(Number(v))) pts.push([xAt(i), yAt(v), Number(v), i]);
      });
      if (!pts.length) return '';
      var d = 'M' + pts[0][0].toFixed(1) + ' ' + pts[0][1].toFixed(1) +
        pts.slice(1).map(function (p) { return ' L' + p[0].toFixed(1) + ' ' + p[1].toFixed(1); }).join('');
      var id = 'wallPath' + (++WALL_CHART_SEQ);
      var nodes = pts.map(function (p) {
        var idx = p[3];
        var nodeTime = labels[idx] || '--:--';
        var title = nodeTime + ' · ' + label + ' ' + wallNum(p[2], label === '健康度' ? '' : '%');
        return '<circle class="wall-node" cx="' + p[0].toFixed(1) + '" cy="' + p[1].toFixed(1) +
          '" r="3.2" fill="' + color + '" style="animation-delay:' + (pts.indexOf(p) * .18).toFixed(2) + 's">' +
          '<title>' + esc(title) + '</title></circle>';
      }).join('');
      return '<path id="' + id + '" class="wall-line" d="' + d + '" stroke="' + color + '"></path>' +
        nodes +
        '<circle class="wall-traveler" r="4" fill="' + color + '" style="color:' + color + '">' +
        '<animateMotion dur="5.5s" repeatCount="indefinite"><mpath href="#' + id + '"></mpath></animateMotion>' +
        '</circle>';
    }
    var latestHealth = null, latestCpu = null, latestMem = null;
    for (var hi = healthValues.length - 1; hi >= 0; hi--) { if (healthValues[hi] !== null && healthValues[hi] !== undefined) { latestHealth = healthValues[hi]; break; } }
    for (var ci = cpuValues.length - 1; ci >= 0; ci--) { if (cpuValues[ci] !== null && cpuValues[ci] !== undefined) { latestCpu = cpuValues[ci]; break; } }
    for (var mi = memoryValues.length - 1; mi >= 0; mi--) { if (memoryValues[mi] !== null && memoryValues[mi] !== undefined) { latestMem = memoryValues[mi]; break; } }
    return '<div class="wall-chart-card">' +
      '<div class="wall-chart-head">' +
        '<span class="wall-live-label"><i></i>实时节点</span>' +
        '<span class="wall-legend" style="--c:' + wallSeriesColor(kind, 'health') + '"><i></i>健康度 ' + esc(wallNum(latestHealth)) + '</span>' +
        '<span class="wall-legend" style="--c:' + wallSeriesColor(kind, 'cpu') + '"><i></i>CPU ' + esc(wallNum(latestCpu, '%')) + '</span>' +
        '<span class="wall-legend" style="--c:' + wallSeriesColor(kind, 'memory') + '"><i></i>内存 ' + esc(wallNum(latestMem, '%')) + '</span>' +
      '</div>' +
      '<div class="wall-chart-body">' +
        '<div class="wall-y-axis"><span>100</span><span>75</span><span>50</span><span>25</span><span>0</span></div>' +
        '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none" class="wall-chart-svg">' +
          '<defs><filter id="wallGlow' + WALL_CHART_SEQ + '"><feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>' +
          grid + series(healthValues, wallSeriesColor(kind, 'health'), '健康度') +
          series(cpuValues, wallSeriesColor(kind, 'cpu'), 'CPU') +
          series(memoryValues, wallSeriesColor(kind, 'memory'), '内存') +
        '</svg>' +
      '</div>' +
      '<div class="wall-axis-labels">' + labels.map(function (x) { return '<span>' + esc(x) + '</span>'; }).join('') + '</div>' +
    '</div>';
  }

  

  

  function wallKindLabel(kind) {
    return { switch: '交换机', server: '服务器', security: '安全设备' }[kind] || '设备';
  }

  function wallIsNoIp(ip) {
    return /^noip-/i.test(String(ip || ''));
  }

  function wallIpLabel(ip) {
    return wallIsNoIp(ip) ? '待配置管理IP' : (ip || '—');
  }

  function wallPortCell(port) {
    var up = port.up === true;
    var state = port.up === null || port.up === undefined ? 'unknown' : (up ? 'up' : 'down');
    var stateText = state === 'up' ? 'UP' : state === 'down' ? 'DOWN' : '未采集';
    var name = port.name || '接口';
    var desc = port.description || '';
    var label = name + ' · ' + stateText + (desc ? ' · ' + desc : '');
    return '<span class="real-port ' + state + '" data-port-name="' + esc(name) +
      '" data-port-state="' + state + '" data-port-desc="' + esc(desc) +
      '" role="button" tabindex="0" title="' + esc(label) + ' 点击放大查看">' +
      '<i></i><em>' + esc(String(name).replace(/^.*\//, 'P')) + '</em></span>';
  }

  function wallPortGrid(item, kind) {
    var ports = item.port_list || [];
    if (!ports.length) return '<div class="real-port-empty">' + (wallIsNoIp(item.ip) ? '尚未配置管理IP，完成接入与采集后显示全部接口状态' : '暂无接口明细，完成一次采集后显示所有接口状态') + '</div>';
    var cls = kind === 'server' ? 'ports-server' : (kind === 'security' ? 'ports-security' : 'ports-switch');
    return '<div class="real-port-grid ' + cls + '">' + ports.map(wallPortCell).join('') + '</div>';
  }

  var WALL_HARDWARE_IMAGES = {
    switch: {
      front: { src: 'assets/images/devices/hq/switch-s12700e4-front-hq.webp', label: '交换机前面板实物图', exact: false },
      back: { src: 'assets/images/devices/hq/switch-s12700e4-rear-hq.webp', label: '同系列交换机后部散热面板参考图', exact: false },
      top: { src: 'assets/images/devices/hq/switch-s12700e4-angle-hq.webp', label: '同系列交换机顶部与侧面立体实物图', exact: false }
    },
    server: {
      front: { src: 'assets/images/devices/hq/server-r750-front-hq.webp', label: '机架服务器前面板实物图', exact: false },
      back: { src: 'assets/images/devices/hq/server-r750-rear-hq.webp', label: '机架服务器后面板参考图', exact: false },
      top: { src: 'assets/images/devices/hq/server-r750-top-hq.webp', label: '机架服务器顶部结构参考图', exact: false }
    },
    security: {
      front: { src: 'assets/images/devices/hq/security-usg6000e-front-hq.webp', label: '安全设备前面板实物图', exact: false },
      back: { src: 'assets/images/devices/hq/security-usg6000e-rear-hq.webp', label: '安全设备后面板参考图', exact: false },
      top: { src: 'assets/images/devices/hq/security-usg6000e-angle-hq.webp', label: '安全设备顶部与侧面立体参考图', exact: false }
    }
  };
  var WALL_MODEL_HARDWARE = {
    switch: [
      {
        match: /S12700E-4/i,
        views: {
          front: { src: 'assets/images/devices/hq/switch-s12700e4-front-hq.webp', label: 'S12700E-4 前面板实物图', exact: true },
          back: { src: 'assets/images/devices/hq/switch-s12700e4-rear-hq.webp', label: 'S12700E-4 后部风扇与散热面板实物图', exact: true },
          top: { src: 'assets/images/devices/hq/switch-s12700e4-angle-hq.webp', label: 'S12700E 系列顶部与侧面立体实物图', exact: false }
        }
      },
      {
        match: /S6730/i,
        views: {
          front: { src: 'assets/images/devices/hq/switch-s6730-hq.webp', label: 'S6730-H48X6C 前面板实物图', exact: true },
          back: { src: 'assets/images/devices/hq/switch-s12700e4-rear-hq.webp', label: '同系列交换机后部散热面板参考图', exact: false },
          top: { src: 'assets/images/devices/hq/switch-s5731-top-hq.webp', label: 'S6730 同系列1U交换机顶部与侧面参考图', exact: false }
        }
      },
      {
        match: /S5731/i,
        views: {
          front: { src: 'assets/images/devices/hq/switch-s5731-front-hq.webp', label: 'S5731-S48T4X 前面板实物图', exact: true },
          back: { src: 'assets/images/devices/hq/switch-s12700e4-rear-hq.webp', label: '同系列交换机后部散热面板参考图', exact: false },
          top: { src: 'assets/images/devices/hq/switch-s5731-top-hq.webp', label: 'S5731-S48T4X 顶部与侧面立体实物图', exact: true }
        }
      },
      {
        match: /S5720|S5700/i,
        views: {
          front: { src: 'assets/images/devices/hq/switch-s5720-hq.webp', label: 'S5720/S5700 系列交换机前面板实物图', exact: false },
          back: { src: 'assets/images/devices/hq/switch-s12700e4-rear-hq.webp', label: '同系列交换机后部散热面板参考图', exact: false },
          top: { src: 'assets/images/devices/hq/switch-s5731-top-hq.webp', label: 'S5720/S5700 同系列1U交换机顶部与侧面参考图', exact: false }
        }
      },
      {
        match: /S2700/i,
        views: {
          front: { src: 'assets/images/devices/hq/switch-s2700-hq.webp', label: 'S2700-26TP-SI-AC 交换机实物图', exact: true },
          back: { src: 'assets/images/devices/hq/switch-s12700e4-rear-hq.webp', label: '同系列交换机后部散热面板参考图', exact: false },
          top: { src: 'assets/images/devices/hq/switch-s5731-top-hq.webp', label: 'S2700 同系列1U交换机顶部与侧面参考图', exact: false }
        }
      },
      {
        match: /AC6605/i,
        views: {
          front: { src: 'assets/images/devices/hq/wireless-ac6605-hq.webp', label: 'AC6605 无线控制器实物图', exact: true },
          back: { src: 'assets/images/devices/hq/switch-s12700e4-rear-hq.webp', label: '无线控制器后部接口参考图', exact: false },
          top: { src: 'assets/images/devices/hq/switch-s5731-top-hq.webp', label: 'AC6605 同系列1U设备顶部与侧面参考图', exact: false }
        }
      }
    ],
    server: [
      {
        match: /R750/i,
        views: {
          front: { src: 'assets/images/devices/hq/server-r750-front-hq.webp', label: 'PowerEdge R750 前面板实物图', exact: true },
          back: { src: 'assets/images/devices/hq/server-r750-rear-hq.webp', label: 'PowerEdge R750 后面板实物图', exact: true },
          top: { src: 'assets/images/devices/hq/server-r750-top-hq.webp', label: 'PowerEdge R750 顶部机箱实物图', exact: true }
        }
      },
      {
        match: /X3650|IBM/i,
        views: {
          front: { src: 'assets/images/devices/hq/server-ibm-x3650-hq.webp', label: 'IBM System x3650 M4 前面板实物图', exact: true },
          back: { src: 'assets/images/devices/hq/server-r750-rear-hq.webp', label: '服务器后面板参考图', exact: false },
          top: { src: 'assets/images/devices/hq/server-r750-top-hq.webp', label: '服务器顶部结构参考图', exact: false }
        }
      },
      {
        match: /VX1200|爱数/i,
        views: {
          front: { src: 'assets/images/devices/hq/server-aishu-vx1200-hq.webp', label: '爱数 VX1200 备份一体机实物图', exact: true },
          back: { src: 'assets/images/devices/hq/server-r750-rear-hq.webp', label: '备份一体机后面板参考图', exact: false },
          top: { src: 'assets/images/devices/hq/server-r750-top-hq.webp', label: '备份一体机顶部结构参考图', exact: false }
        }
      },
      {
        match: /aServer-R-2205/i,
        views: {
          front: { src: 'assets/images/devices/hq/server-aserver-hq.webp', label: '深信服 aServer-R-2205 前面板实物图', exact: true },
          back: { src: 'assets/images/devices/hq/server-r750-rear-hq.webp', label: '超融合服务器后面板参考图', exact: false },
          top: { src: 'assets/images/devices/hq/server-r750-top-hq.webp', label: '超融合服务器顶部结构参考图', exact: false }
        }
      },
      {
        match: /超聚变|2288H/i,
        views: {
          front: { src: 'assets/images/devices/hq/server-fusion2288h-hq.webp', label: '超聚变 FusionServer 机架服务器实物图', exact: false },
          back: { src: 'assets/images/devices/hq/server-r750-rear-hq.webp', label: '服务器后面板参考图', exact: false },
          top: { src: 'assets/images/devices/hq/server-r750-top-hq.webp', label: '服务器顶部结构参考图', exact: false }
        }
      }
    ],
    security: [
      {
        match: /USG(6000E|6650E)/i,
        views: {
          front: { src: 'assets/images/devices/hq/security-usg6000e-front-hq.webp', label: 'USG6000E/6650E 系列前面板实物图', exact: true },
          back: { src: 'assets/images/devices/hq/security-usg6000e-rear-hq.webp', label: 'USG6000E/6650E 系列后面板实物图', exact: true },
          top: { src: 'assets/images/devices/hq/security-usg6000e-angle-hq.webp', label: 'USG6000E/6650E 系列顶部与侧面立体实物图', exact: true }
        }
      },
      {
        match: /USG6655E|USG6655/i,
        views: {
          front: { src: 'assets/images/devices/hq/security-usg6000e-front-hq.webp', label: 'USG6655E 同系列前面板实物图', exact: false },
          back: { src: 'assets/images/devices/hq/security-usg6000e-rear-hq.webp', label: 'USG6655E 同系列后面板实物图', exact: false },
          top: { src: 'assets/images/devices/hq/security-usg6000e-angle-hq.webp', label: 'USG6655E 同系列顶部与侧面实物图', exact: false }
        }
      },
      {
        match: /Sangfor|sanfor|AF8\.0|STA-100|Sq-6390|SIP-logger|深信服|北信源|入侵防御|态势感知/i,
        views: {
          front: { src: 'assets/images/devices/hq/security-sangfor-hq.webp', label: '同类安全设备前面板实物图', exact: false },
          back: { src: 'assets/images/devices/hq/security-usg6000e-rear-hq.webp', label: '同类安全设备后面板参考图', exact: false },
          top: { src: 'assets/images/devices/hq/security-usg6000e-angle-hq.webp', label: '同类安全设备顶部与侧面立体参考图', exact: false }
        }
      }
    ]
  };

  function wallHardwareView(item, kind, face) {
    var model = String(item.model || '');
    var variants = WALL_MODEL_HARDWARE[kind] || [];
    var matched = null;
    for (var i = 0; i < variants.length; i++) {
      if (variants[i].match.test(model)) { matched = variants[i].views; break; }
    }
    var cfg = matched || WALL_HARDWARE_IMAGES[kind] || WALL_HARDWARE_IMAGES.switch;
    return cfg[face] || cfg.front;
  }

  function wallHardwareStage(item, kind) {
    var front = wallHardwareView(item, kind, 'front');
    var back = wallHardwareView(item, kind, 'back');
    var top = wallHardwareView(item, kind, 'top');
    var ports = item.port_list || [];
    var up = ports.filter(function (p) { return p.up === true; }).length;
    var down = ports.filter(function (p) { return p.up === false; }).length;
    var unknown = Math.max(0, ports.length - up - down);
    var badgeText = front.exact ? '高清真机实拍' : '高清同系列实拍参考';
    var alt = item.name || '设备';
    function face(cls, view) {
      return '<div class="hardware-3d-face ' + cls + '"><img src="' + view.src + '" alt="' + esc(alt + ' ' + view.label) +
        '" draggable="false" loading="eager" decoding="async" fetchpriority="high"></div>';
    }
    return '<div class="hardware-stage">' +
      '<div class="hardware-photo-frame hardware-viewer" data-hardware-viewer tabindex="0" aria-label="三维设备查看器，可拖动旋转和滚轮缩放">' +
        '<div class="hardware-viewer-toolbar">' +
          '<span class="hardware-view-state" data-hw-view-label>高清 3D 立体视图</span>' +
          '<span class="hardware-view-presets">' +
            '<button type="button" data-hw-preset="iso">立体</button>' +
            '<button type="button" data-hw-preset="front">前面板</button>' +
            '<button type="button" data-hw-preset="back">后面板</button>' +
          '</span>' +
          '<span class="hardware-view-hint">拖动旋转 · 滚轮缩放 · 双击复位</span>' +
          '<button type="button" class="hardware-reset" data-hw-reset>复位</button>' +
          '<span class="hardware-zoom" data-hw-zoom>100%</span>' +
        '</div>' +
        '<div class="hardware-photo-glow"></div>' +
        '<div class="hardware-viewer-world" data-hardware-world>' +
          '<div class="hardware-3d-box kind-' + esc(kind) + '">' +
            face('hw-front', front) + face('hw-back', back) + face('hw-top', top) +
            '<div class="hardware-3d-side hw-left"></div><div class="hardware-3d-side hw-right"></div>' +
            '<div class="hardware-3d-side hw-bottom"></div>' +
          '</div>' +
        '</div>' +
        '<span class="hardware-photo-badge"><i></i>' + badgeText + '</span>' +
        '<span class="hardware-photo-model">' + esc(item.model || wallKindLabel(kind)) + '</span>' +
      '</div>' +
      '<div class="hardware-photo-caption"><span>' + esc(front.label) + '</span><b class="mono">' + up + ' UP · ' + down + ' DOWN · ' + unknown + ' 未采集</b></div>' +
      '<div class="hardware-port-panel">' +
        '<div class="hardware-port-head"><span>接口实时状态 <em>点击接口可放大查看</em></span><b>' + ports.length + ' 口</b></div>' +
        wallPortGrid(item, kind) +
      '</div>' +
    '</div>';
  }

  function bindHardwareViewer(host, item, kind) {
    var viewer = host ? host.querySelector('[data-hardware-viewer]') : null;
    var world = host ? host.querySelector('[data-hardware-world]') : null;
    if (!viewer || !world) return;
    var zoomEl = viewer.querySelector('[data-hw-zoom]');
    var viewEl = viewer.querySelector('[data-hw-view-label]');
    var resetBtn = viewer.querySelector('[data-hw-reset]');
    var topFace = viewer.querySelector('.hw-top');
    var frontFace = viewer.querySelector('.hw-front');
    var backFace = viewer.querySelector('.hw-back');
    var box = viewer.querySelector('.hardware-3d-box');
    var frontImg = viewer.querySelector('.hw-front img');
    var layoutFrame = 0;
    function layoutBox() {
      if (!box || !frontImg || !frontImg.naturalWidth || !frontImg.naturalHeight) return;
      var vw = viewer.clientWidth || viewer.getBoundingClientRect().width;
      var vh = viewer.clientHeight || viewer.getBoundingClientRect().height;
      if (!vw || !vh) return;
      var ratio = frontImg.naturalWidth / frontImg.naturalHeight;
      var maxW = Math.max(260, vw * 0.90);
      var maxH = Math.max(150, vh * 0.76);
      var boxW = maxW, boxH = boxW / ratio;
      if (boxH > maxH) { boxH = maxH; boxW = boxH * ratio; }
      boxW = Math.max(150, boxW); boxH = Math.max(64, boxH);
      var depth = Math.max(62, Math.min(122, boxH * 0.88));
      box.style.width = boxW.toFixed(1) + 'px';
      box.style.height = boxH.toFixed(1) + 'px';
      box.style.setProperty('--depth', depth.toFixed(1) + 'px');
      box.style.setProperty('--half-depth', (depth / 2).toFixed(1) + 'px');
      box.style.setProperty('--half-w', (boxW / 2).toFixed(1) + 'px');
      box.style.setProperty('--half-h', (boxH / 2).toFixed(1) + 'px');
    }
    function scheduleLayout() {
      if (layoutFrame) cancelAnimationFrame(layoutFrame);
      layoutFrame = requestAnimationFrame(function () {
        layoutFrame = requestAnimationFrame(layoutBox);
      });
    }
    if (STATE.wallHwObserver) { try { STATE.wallHwObserver.disconnect(); } catch (err) {} }
    if (window.ResizeObserver) {
      STATE.wallHwObserver = new ResizeObserver(scheduleLayout);
      STATE.wallHwObserver.observe(viewer);
    }
    var savedView = STATE.wall3d && item && STATE.wall3d.ip === item.ip ? STATE.wall3d : null;
    var rotX = savedView ? savedView.rotX : -7;
    var rotY = savedView ? savedView.rotY : -11;
    var scale = savedView ? savedView.scale : 1;
    var dragging = false, moved = false, startX = 0, startY = 0, baseX = 0, baseY = 0;

    function viewLabel() {
      var y = ((rotY % 360) + 360) % 360;
      if (rotX < -32) return '高清顶部面板';
      if (y <= 28 || y >= 332) return '高清前面板';
      if (y >= 152 && y <= 208) return '高清后面板';
      return '高清 3D 立体视图';
    }
    function apply() {
      world.style.transform = 'rotateX(' + rotX.toFixed(2) + 'deg) rotateY(' + rotY.toFixed(2) + 'deg) scale(' + scale.toFixed(3) + ')';
      var topBlend = rotX < -18 ? Math.min(1, (-rotX - 18) / 28) : 0;
      if (topFace) topFace.style.opacity = topBlend.toFixed(3);
      if (frontFace) frontFace.style.opacity = (1 - topBlend).toFixed(3);
      if (backFace) backFace.style.opacity = (1 - topBlend).toFixed(3);
      if (zoomEl) zoomEl.textContent = Math.round(scale * 100) + '%';
      if (viewEl) viewEl.textContent = viewLabel();
      STATE.wall3d = { ip: item ? item.ip : '', rotX: rotX, rotY: rotY, scale: scale };
    }
    function reset() {
      rotX = -7; rotY = -11; scale = 1; apply();
    }
    function setPreset(name) {
      if (name === 'front') { rotX = 0; rotY = 0; scale = 1; }
      else if (name === 'back') { rotX = 0; rotY = 180; scale = 1; }
      else if (name === 'top') { rotX = -58; rotY = 0; scale = 1; }
      else { rotX = -7; rotY = -11; scale = 1; }
      apply();
    }
    function stopDrag(e) {
      if (!dragging) return;
      dragging = false; viewer.classList.remove('dragging');
      try { viewer.releasePointerCapture(e.pointerId); } catch (err) {}
      if (!moved) viewer.focus();
    }

    viewer.addEventListener('pointerdown', function (e) {
      if (e.button !== 0 || e.target.closest('button')) return;
      dragging = true; moved = false; startX = e.clientX; startY = e.clientY;
      baseX = rotX; baseY = rotY; viewer.classList.add('dragging');
      try { viewer.setPointerCapture(e.pointerId); } catch (err) {}
      e.preventDefault();
    });
    viewer.addEventListener('pointermove', function (e) {
      if (!dragging) return;
      var dx = e.clientX - startX, dy = e.clientY - startY;
      if (Math.abs(dx) + Math.abs(dy) > 3) moved = true;
      rotY = baseY + dx * 0.42;
      rotX = Math.max(-62, Math.min(12, baseX + dy * 0.32));
      apply();
    });
    viewer.addEventListener('pointerup', stopDrag);
    viewer.addEventListener('pointercancel', stopDrag);
    viewer.addEventListener('wheel', function (e) {
      e.preventDefault();
      scale = Math.max(0.72, Math.min(3.0, scale * (e.deltaY < 0 ? 1.08 : 0.92)));
      apply();
    }, { passive: false });
    viewer.addEventListener('dblclick', reset);
    if (resetBtn) resetBtn.addEventListener('click', reset);
    Array.prototype.forEach.call(viewer.querySelectorAll('[data-hw-preset]'), function (btn) {
      btn.addEventListener('click', function () { setPreset(btn.getAttribute('data-hw-preset')); });
    });
    if (frontImg) {
      if (frontImg.complete) scheduleLayout();
      else frontImg.addEventListener('load', scheduleLayout, { once: true });
    }
    viewer.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowLeft') { rotY -= 8; apply(); e.preventDefault(); }
      else if (e.key === 'ArrowRight') { rotY += 8; apply(); e.preventDefault(); }
      else if (e.key === 'ArrowUp') { rotX = Math.max(-72, rotX - 6); apply(); e.preventDefault(); }
      else if (e.key === 'ArrowDown') { rotX = Math.min(12, rotX + 6); apply(); e.preventDefault(); }
      else if (e.key === '0') { reset(); e.preventDefault(); }
    });
    apply();
    scheduleLayout();
  }

  function openWallPortInspector(cell, item) {
    var name = cell.getAttribute('data-port-name') || '接口';
    var state = cell.getAttribute('data-port-state') || 'unknown';
    var desc = cell.getAttribute('data-port-desc') || '';
    var stateText = state === 'up' ? 'UP · 已连接' : state === 'down' ? 'DOWN · 未连接' : '未采集';
    var tone = state === 'up' ? '#22c55e' : state === 'down' ? '#ef4444' : '#64748b';
    var device = item || {};
    var inner = '<div class="modal port-inspector-modal">' +
      '<div class="card-head"><div class="t"><div class="title" style="font-size:18px">接口放大查看</div>' +
      '<div class="sub">' + esc(device.name || '') + ' · ' + esc(wallIpLabel(device.ip || '')) + '</div></div>' +
      '<button class="icon-btn" style="width:32px;height:32px" data-overlay-cancel>' + icon('close', 16) + '</button></div>' +
      '<div class="port-inspector-hero" style="--port-tone:' + tone + '">' +
        '<div class="port-inspector-jack"><i></i><em>RJ45</em></div>' +
        '<div class="port-inspector-copy"><span class="port-inspector-state">' + esc(stateText) + '</span>' +
          '<h3>' + esc(name) + '</h3><p>' + esc(desc || '暂无接口描述') + '</p></div>' +
      '</div>' +
      '<div class="port-inspector-grid">' +
        '<div><span>所属设备</span><b>' + esc(device.name || '—') + '</b></div>' +
        '<div><span>设备型号</span><b>' + esc(device.model || '—') + '</b></div>' +
        '<div><span>接口状态</span><b style="color:' + tone + '">' + esc(stateText) + '</b></div>' +
        '<div><span>最近巡检</span><b>' + esc(device.last_inspected || '尚未巡检') + '</b></div>' +
      '</div>' +
      '<div class="footer-bar"><span class="kpi-trend">接口详情来自最近一次采集，可在设备采集中刷新</span>' +
      '<button class="btn btn-ghost" data-overlay-cancel>关闭</button></div></div>';
    showOverlay(inner, false);
  }

  function wallDonut(label, value, color) {
    var p = wallPct(value);
    var text = value === null || value === undefined ? '—' : wallNum(value, '%');
    return '<div class="wall-res-stat"><div class="wall-res-donut" style="--p:' + (p === null ? 0 : p) + ';--c:' + color + '"><b>' + esc(text) + '</b></div><span>' + esc(label) + '</span></div>';
  }

  function wallResourceStats(item, kind) {
    var ports = item.port_list || [];
    var totalPorts = ports.length;
    var upPorts = ports.filter(function (p) { return p.up === true; }).length;
    var portPct = totalPorts ? upPorts * 100 / totalPorts : null;
    if (kind === 'server') {
      return wallDonut('健康度', item.health_score, wallScoreTone(item.health_score)) +
        wallDonut('CPU', item.cpu, '#a78bfa') + wallDonut('内存', item.memory, '#60a5fa') +
        wallDonut('磁盘', item.disk, '#34d399');
    }
    return wallDonut('健康度', item.health_score, wallScoreTone(item.health_score)) +
      wallDonut('CPU', item.cpu, kind === 'security' ? '#f59e0b' : '#38bdf8') +
      wallDonut('内存', item.memory, kind === 'security' ? '#fb7185' : '#2dd4bf') +
      wallDonut('接口可用率', portPct, '#22c55e');
  }

  function wallAlertStats(item) {
    var trend = item.alert_trend || { labels: [], values: [] };
    var values = trend.values || [];
    var max = Math.max.apply(null, [1].concat(values));
    var bars = values.map(function (v, i) {
      var h = Math.max(4, Math.round(Number(v) / max * 62));
      return '<span class="wall-alert-bar" style="height:' + h + 'px" title="' + esc((trend.labels || [])[i] || '') + ' · ' + v + ' 条"><i></i></span>';
    }).join('');
    var sev = item.alert_by_severity || {};
    var recent = item.recent_alerts || [];
    return '<div class="wall-alert-card">' +
      '<div class="wall-alert-head"><span><i class="live-dot"></i>告警实时抓取</span><span class="mono">近 6 小时</span></div>' +
      '<div class="wall-alert-bars">' + (bars || '<span class="wall-chart-empty">暂无告警</span>') + '</div>' +
      '<div class="wall-alert-axis">' + (trend.labels || []).filter(function (_, i) { return i % 3 === 0; }).map(function (x) { return '<span>' + esc(x) + '</span>'; }).join('') + '</div>' +
      '<div class="wall-severity-row"><span class="critical">紧急 ' + (sev.critical || 0) + '</span><span class="major">严重 ' + (sev.major || 0) + '</span><span class="warning">警告 ' + (sev.warning || 0) + '</span><span class="info">提示 ' + (sev.info || 0) + '</span></div>' +
      '<div class="wall-recent-alerts">' + (recent.length ? recent.slice(0, 4).map(function (a) {
        return '<div><span>' + esc(a.severity || '告警') + '</span><b>' + esc(a.content || '') + '</b><em>' + esc(a.time || '') + '</em></div>';
      }).join('') : '<div class="empty">当前没有未恢复告警</div>') + '</div>' +
    '</div>';
  }

  function wallDeviceDetail(item, kind) {
    var online = item.online;
    var noIp = wallIsNoIp(item.ip);
    var health = item.health_score === null || item.health_score === undefined ? '—' : wallNum(item.health_score);
    return '<div class="wall-device-page">' +
      '<div class="wall-device-title">' +
        '<div><div class="wall-device-name">' + esc(item.name) + '<span class="ws-type">' + esc(item.type_label) + '</span></div>' +
        '<div class="wall-device-sub"><span class="ws-dot ' + (noIp ? 'pending' : (online ? 'on' : 'off')) + '"></span>' + (noIp ? '台账设备 · 待配置管理IP' : (online ? '在线' : '离线')) + ' · <span class="mono">' + esc(wallIpLabel(item.ip)) + '</span> · ' + esc(item.model || '—') + ' · ' + esc(item.group || '—') + '</div></div>' +
        '<div class="wall-device-health" style="--c:' + wallScoreTone(item.health_score) + '">健康度 <b>' + esc(health) + '</b></div>' +
      '</div>' +
      '<div class="wall-device-body">' +
        '<section class="wall-device-visual">' +
          wallHardwareStage(item, kind) +
        '</section>' +
        '<aside class="wall-device-side">' +
          '<div class="wall-resource-row">' + wallResourceStats(item, kind) + '</div>' +
          wallTrendChart(item, kind) +
          wallAlertStats(item) +
        '</aside>' +
      '</div>' +
      '<div class="wall-device-foot">最近巡检 ' + esc(item.last_inspected || '—') + ' · 配置备份 ' + wallNum(item.backups, ' 份') + ' · 未恢复告警 ' + wallNum(item.unresolved, ' 条') + ' · 数据源：本平台自带采集</div>' +
    '</div>';
  }

  function wallTabsHtml(data) {
    var counts = data.summary || {};
    return ['switch', 'server', 'security'].map(function (kind) {
      var label = wallKindLabel(kind);
      var active = STATE.wallCategory === kind;
      return '<button data-wall-kind="' + kind + '" class="' + (active ? 'active' : '') + '"><i class="kind-dot ' + kind + '"></i>' + label + '<b>' + (counts[kind] || 0) + '</b></button>';
    }).join('');
  }

  function pageWall(data) {
    var sum = data.summary || {};
    return '<div class="wall wall-single">' +
      '<div class="wall-head wall-single-head">' +
        '<div class="wh-left"><div class="wh-title">网络设备巡检大屏</div><div class="wh-sub">单设备全屏巡检 · 高清真机实拍 · 3D 面板立体视图 · 实时资源与告警</div></div>' +
        '<div class="wh-mid" id="wallSummary"><span><b>' + (sum.devices || 0) + '</b> 台设备</span><span><b class="ok">' + (sum.online || 0) + '</b> 在线</span><span><b class="warn">' + (sum.alerts || 0) + '</b> 未恢复告警</span></div>' +
        '<div class="wh-right"><span class="wh-time" id="wallUpdated">更新 ' + esc(data.generated_at || '') + '</span><button class="btn btn-ghost sm" id="wallFull">全屏</button><button class="btn btn-ghost sm" id="wallExit">退出大屏</button></div>' +
      '</div>' +
      '<div class="wall-control-bar"><div class="wall-category-block"><span class="wall-control-label">设备分类</span><div class="wall-kind-tabs" id="wallCategoryTabs">' + wallTabsHtml(data) + '</div></div>' +
        '<div class="wall-device-picker"><label>选择具体设备</label><select id="wallDeviceSelect"></select></div>' +
        '<button class="btn btn-ghost sm" id="wallAuto">自动轮播：关闭</button><span class="wall-live-status" id="wallLiveStatus"><i></i>实时数据</span></div>' +
      '<div id="wallDetail" class="wall-detail"></div>' +
    '</div>';
  }

  function bindWall(data) {
    var wallData = data;
    var timers = [];
    STATE.wallCategory = ['switch', 'server', 'security'].indexOf(STATE.wallCategory) >= 0 ? STATE.wallCategory : 'switch';
    if (!STATE.wallAuto) STATE.wallAuto = false;
    if (!STATE.wallFace) STATE.wallFace = 'front';
    var detail = document.getElementById('wallDetail');
    var catHost = document.getElementById('wallCategoryTabs');
    var select = document.getElementById('wallDeviceSelect');
    var autoBtn = document.getElementById('wallAuto');
    var summary = document.getElementById('wallSummary');
    var updated = document.getElementById('wallUpdated');
    var live = document.getElementById('wallLiveStatus');
    var currentItem = null;
    var refreshTimer = null;

    function rowsOf(kind) { return wallData[kind] || []; }
    function selectedRows() { return rowsOf(STATE.wallCategory); }
    function normalizeDevice() {
      var rows = selectedRows();
      var exists = rows.some(function (x) { return x.ip === STATE.wallDevice; });
      if (!exists) STATE.wallDevice = rows.length ? rows[0].ip : '';
    }
    function fillControls() {
      normalizeDevice();
      if (catHost) catHost.innerHTML = wallTabsHtml(wallData);
      if (select) {
        var rows = selectedRows();
        select.innerHTML = rows.length ? rows.map(function (x) {
          return '<option value="' + esc(x.ip) + '"' + (x.ip === STATE.wallDevice ? ' selected' : '') + '>' +
            esc(x.name) + ' · ' + esc(wallIpLabel(x.ip)) + ' · 健康度 ' + esc(wallNum(x.health_score)) + '</option>';
        }).join('') : '<option value="">当前分类暂无设备</option>';
        select.disabled = !rows.length;
      }
      if (autoBtn) autoBtn.textContent = '自动轮播：' + (STATE.wallAuto ? '开启' : '关闭');
      if (autoBtn) autoBtn.classList.toggle('on', !!STATE.wallAuto);
      if (summary) summary.innerHTML = '<span><b>' + ((wallData.summary || {}).devices || 0) + '</b> 台设备</span><span><b class="ok">' + ((wallData.summary || {}).online || 0) + '</b> 在线</span><span><b class="warn">' + ((wallData.summary || {}).alerts || 0) + '</b> 未恢复告警</span>';
      if (updated) updated.textContent = '更新 ' + (wallData.generated_at || '');
      if (live) live.innerHTML = '<i></i>实时数据 · ' + new Date().toLocaleTimeString('zh-CN', { hour12: false });
    }
    function renderDetail() {
      normalizeDevice();
      var rows = selectedRows();
      var item = rows.filter(function (x) { return x.ip === STATE.wallDevice; })[0];
      currentItem = item || null;
      if (detail) detail.innerHTML = item ? wallDeviceDetail(item, STATE.wallCategory) :
        '<div class="wall-detail-empty">当前分类暂无设备<br/><small>请到设备清单录入设备并完成一次采集</small></div>';
      if (item && detail) bindHardwareViewer(detail, item, STATE.wallCategory);
    }
    function stopTimers() { timers.forEach(function (t) { try { t.stop(); } catch (e) {} }); timers = []; }
    fillControls(); renderDetail();

    if (detail) {
      detail.addEventListener('click', function (e) {
        var cell = e.target.closest('.real-port[data-port-name]');
        if (cell) openWallPortInspector(cell, currentItem);
      });
      detail.addEventListener('keydown', function (e) {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        var cell = e.target.closest('.real-port[data-port-name]');
        if (!cell) return;
        e.preventDefault();
        openWallPortInspector(cell, currentItem);
      });
    }

    if (catHost) catHost.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-wall-kind]');
      if (!btn) return;
      STATE.wallCategory = btn.getAttribute('data-wall-kind');
      STATE.wallDevice = '';
      STATE.wallFace = 'front';
      STATE.wallAuto = false;
      fillControls(); renderDetail();
    });
    if (select) select.addEventListener('change', function () {
      STATE.wallDevice = select.value;
      STATE.wallAuto = false;
      fillControls(); renderDetail();
    });
    if (autoBtn) autoBtn.addEventListener('click', function () {
      STATE.wallAuto = !STATE.wallAuto;
      fillControls();
      if (STATE.wallAuto) {
        var rows = selectedRows();
        if (rows.length > 1) {
          var idx = rows.findIndex(function (x) { return x.ip === STATE.wallDevice; });
          STATE.wallDevice = rows[(idx + 1) % rows.length].ip;
          fillControls(); renderDetail();
        }
      }
    });

    var refresh = function () {
      window.NetInspect.wall().then(function (fresh) {
        wallData = fresh;
        fillControls(); renderDetail();
      }).catch(function () {});
    };
    refreshTimer = setInterval(refresh, 15000);
    timers.push({ stop: function () { clearInterval(refreshTimer); } });
    var rotateTimer = setInterval(function () {
      if (!STATE.wallAuto) return;
      var rows = selectedRows();
      if (rows.length < 2) return;
      var idx = rows.findIndex(function (x) { return x.ip === STATE.wallDevice; });
      STATE.wallDevice = rows[(idx + 1) % rows.length].ip;
      fillControls(); renderDetail();
    }, Math.max(5, Number(data.rotate_seconds) || 8) * 1000);
    timers.push({ stop: function () { clearInterval(rotateTimer); } });
    STATE.wallTimers = timers;

    var full = document.getElementById('wallFull');
    if (full) full.addEventListener('click', function () {
      try { document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen(); }
      catch (e) { showToast('当前浏览器不支持全屏'); }
    });
    var exit = document.getElementById('wallExit');
    if (exit) exit.addEventListener('click', function () { location.href = '#/overview'; });
  }

  /* ---------- 页面：全局检索 ---------- */
  function pageGlobalSearch(data) {
    var kw = data.keyword || '';
    var devices = data.devices || [], alerts = data.alerts || [], inspections = data.inspections || [];
    var backups = data.backups || [], reports = data.reports || [], logs = data.logs || [];
    var groups = [{key:'devices',label:'设备',count:devices.length}, {key:'alerts',label:'告警',count:alerts.length},
      {key:'inspections',label:'巡检',count:inspections.length}, {key:'backups',label:'备份',count:backups.length},
      {key:'reports',label:'报告',count:reports.length}, {key:'logs',label:'日志',count:logs.length}].filter(function (g) { return g.count > 0; });
    var requested = parseQuery((location.hash.split('?')[1] || '')).kind;
    var searchKind = requested === 'all' || groups.some(function (g) { return g.key === requested; }) ? requested : (groups[0] || {}).key;
    var filter = '<div class="module-filter-block"><div class="form-row module-filter-row">' +
      field('全局关键词', textBox('gsKeyword', kw, '设备 / IP / 资产编号 / 责任人 / 告警 / 巡检 / 报告')) +
      '</div><div class="btn-group"><button class="btn btn-ghost sm" id="gsReset">清空</button>' +
      '<button class="btn btn-primary sm" id="gsQuery">检索</button></div></div>';
    var html = '<div class="search-query">' + filter + '</div>' +
      (groups.length ? '<div class="search-category-bar" role="tablist" aria-label="检索结果类别">' + [{key:'all',label:'全部',count:data.total || 0}].concat(groups).map(function (g) {
        return '<button type="button" role="tab" aria-selected="' + (g.key === searchKind ? 'true' : 'false') + '" data-search-kind="' + g.key + '">' + esc(g.label) + ' <b>' + esc(g.count) + '</b></button>';
      }).join('') + '</div>' : '');
    if (!kw) {
      return topbar() + '<div class="page-head"><div class="page-title"><h1>全局检索</h1>' +
        '<div class="page-sub"><span>搜索设备、告警、巡检、备份、报告与日志</span></div></div></div>' + html;
    }
    if (devices.length && (searchKind === 'all' || searchKind === 'devices')) {
      var dc = [{ text: '设备名称', width: 220 }, { text: 'IP', width: 130 }, { text: '类型', width: 120 },
        { text: '责任人', width: 110 }, { text: '资产编号', width: 130 }, { text: '健康状态', width: 110 }, { text: '操作', width: 80 }];
      var dr = devices.map(function (d) {
        return [{ text: d.name || '—', cls: 'strong' }, { text: d.ip || '—', cls: 'mono' }, { text: d.type_label || '—' },
          { text: d.owner || '—' }, { text: d.asset_no || '—', cls: 'mono' },
          { html: tag(d.health_label || '未巡检', d.health_tone || 'neutral') },
          { html: '<a class="link" href="#/devices?ip=' + encodeURIComponent(d.ip || '') + '">进入</a>' }];
      });
      html += '<div class="card tight overview-module-card">' + cardHead('设备', '命中 ' + devices.length + ' 台', '') +
        '<div style="overflow-x:auto">' + table(dc, dr) + '</div></div>';
    }
    if (alerts.length && (searchKind === 'all' || searchKind === 'alerts')) {
      var ac = [{ text: '告警内容' }, { text: '设备', width: 160 }, { text: '级别', width: 90 }, { text: '状态', width: 90 }, { text: '时间', width: 160 }, { text: '操作', width: 80 }];
      var ar = alerts.map(function (a) {
        return [{ text: a.title || '—', cls: 'strong' }, { text: a.device || '—' }, { text: a.severity_label || '—' },
          { text: a.status || '—' }, { text: a.time || '—', cls: 'mono' }, { html: '<a class="link" href="#/alerts?device=' + encodeURIComponent(a.device_ip || a.device || '') + '">进入</a>' }];
      });
      html += '<div class="card tight overview-module-card">' + cardHead('告警', '命中 ' + alerts.length + ' 条', '') +
        '<div style="overflow-x:auto">' + table(ac, ar) + '</div></div>';
    }
    if (inspections.length && (searchKind === 'all' || searchKind === 'inspections')) {
      var ic = [{ text: '巡检对象', width: 210 }, { text: '类型', width: 120 }, { text: '时间', width: 170 }, { text: '责任人', width: 110 }, { text: '健康度', width: 90 }, { text: '状态', width: 90 }, { text: '操作', width: 80 }];
      var ir = inspections.map(function (x) {
        return [{ text: x.device || '—', cls: 'strong' }, { text: x.type || '—' }, { text: x.time || '—', cls: 'mono' },
          { text: x.owner || '—' }, { text: x.score === null ? '—' : String(x.score), cls: 'mono' },
          { html: tag(x.label || '—', x.tone || 'neutral') }, { html: '<a class="link" href="#/overview?tab=inspections">进入</a>' }];
      });
      html += '<div class="card tight overview-module-card">' + cardHead('巡检记录', '命中 ' + inspections.length + ' 条', '') +
        '<div style="overflow-x:auto">' + table(ic, ir) + '</div></div>';
    }
    if (backups.length && (searchKind === 'all' || searchKind === 'backups')) {
      var bc = [{ text: '备份文件' }, { text: '设备 IP', width: 140 }, { text: '大小', width: 100 }, { text: '时间', width: 170 }, { text: '操作', width: 80 }];
      var br = backups.map(function (x) { return [{ text: x.name || '—', cls: 'strong' }, { text: x.device_ip || '—', cls: 'mono' },
        { text: x.size_text || '—' }, { text: x.time || '—', cls: 'mono' }, { html: '<a class="link" href="#/backup?keyword=' + encodeURIComponent(x.device_ip || '') + '">进入</a>' }]; });
      html += '<div class="card tight overview-module-card">' + cardHead('配置备份', '命中 ' + backups.length + ' 条', '') + '<div style="overflow-x:auto">' + table(bc, br) + '</div></div>';
    }
    if (reports.length && (searchKind === 'all' || searchKind === 'reports')) {
      var rc = [{ text: '报告文件' }, { text: '类型', width: 120 }, { text: '导出人', width: 100 }, { text: '时间', width: 170 }, { text: '操作', width: 80 }];
      var rr = reports.map(function (x) { return [{ text: x.filename || '—', cls: 'strong' }, { text: x.kind || '—' },
        { text: x.operator || '—' }, { text: x.created_at || '—', cls: 'mono' }, { html: '<a class="link" href="#/reports?keyword=' + encodeURIComponent(x.filename || '') + '">进入</a>' }]; });
      html += '<div class="card tight overview-module-card">' + cardHead('报告归档', '命中 ' + reports.length + ' 条', '') + '<div style="overflow-x:auto">' + table(rc, rr) + '</div></div>';
    }
    if (logs.length && (searchKind === 'all' || searchKind === 'logs')) {
      var lc = [{ text: '时间', width: 165 }, { text: '设备', width: 160 }, { text: 'IP', width: 125 }, { text: '摘要' }, { text: '操作', width: 80 }];
      var lr = logs.map(function (x) { return [{ text: x.created_at || '—', cls: 'mono' }, { text: x.device_name || '—', cls: 'strong' },
        { text: x.device_ip || '—', cls: 'mono' }, { text: x.summary || x.reason || '—' }, { html: '<a class="link" href="#/pending?tab=logs&ip=' + encodeURIComponent(x.device_ip || '') + '">进入</a>' }]; });
      html += '<div class="card tight overview-module-card">' + cardHead('日志', '命中 ' + logs.length + ' 条', '') + '<div style="overflow-x:auto">' + table(lc, lr) + '</div></div>';
    }
    if (!(devices.length || alerts.length || inspections.length || backups.length || reports.length || logs.length)) {
      html += notice('没有找到匹配对象，请缩短关键词后重试。');
    }
    return topbar() + '<div class="page-head"><div class="page-title"><h1>全局检索</h1>' +
      '<div class="page-sub"><span>按类别查看匹配结果</span></div></div></div>' + html;
  }

  function bindGlobalSearchPage() {
    Array.prototype.forEach.call(document.querySelectorAll('[data-search-kind]'), function (node) {
      node.addEventListener('click', function () {
        var keyword = ((document.getElementById('gsKeyword') || {}).value || '').trim();
        refreshPageHash('search', 'q=' + encodeURIComponent(keyword) + '&kind=' + encodeURIComponent(node.getAttribute('data-search-kind')));
      });
    });
    var go = function () {
      var kw = ((document.getElementById('gsKeyword') || {}).value || '').trim();
      refreshPageHash('search', kw ? 'q=' + encodeURIComponent(kw) : '');
    };
    var q = document.getElementById('gsQuery'); if (q) q.addEventListener('click', go);
    var box = document.getElementById('gsKeyword'); if (box) box.addEventListener('keydown', function (e) { if (e.key === 'Enter') go(); });
    var reset = document.getElementById('gsReset'); if (reset) reset.addEventListener('click', function () { refreshPageHash('search', ''); });
  }

  /* ---------- 页面注册表：load（取数） + render（原型结构） + bind（交互） ---------- */
  var PAGE_DEVICE_KEY = { server: 'svDevice', switch: 'swDevice' };

  var PAGES = {
    search: {
      title: '全局检索',
      load: function (query) { return window.NetInspect.search(query.q || '', 50); },
      render: pageGlobalSearch, bind: bindGlobalSearchPage
    },
    overview: {
      title: '巡检总览',
      load: function () { return window.NetInspect.overview(STATE.days); },
      render: pageOverview, bind: bindOverview
    },
    wall: {
      title: '巡检大屏',
      load: function () { return window.NetInspect.wall(); },
      render: pageWall, bind: bindWall
    },
    alerts: {
      title: '聚合告警',
      load: function () {
        var a = STATE.alerts || {};
        return window.NetInspect.alerts({ hours: a.hours, severity: a.severity,
          status: a.status, keyword: a.keyword, device: a.device, limit: a.limit || 200 });
      },
      render: pageAlerts, bind: bindAlerts
    },
    pending: {
      title: '设备采集中心',
      load: function () {
        var p = STATE.pending;
        var f = STATE.collectFilter || {};
        return Promise.all([
          window.NetInspect.devices({ pending: 1, keyword: p.keyword,
            page: p.page, page_size: p.page_size, sort: p.sort, order: p.order }),
          window.NetInspect.remoteCredentials().catch(function (err) { return { credentials: [], load_error: '凭据状态读取失败：' + err.message }; }),
          window.NetInspect.collectOverview({ pending_only: 1 }).catch(function (err) { return { devices: [], runs: [], last_logs: [], settings: {}, stats: {}, load_error: '采集概览读取失败：' + err.message }; }),
          window.NetInspect.collectLogs({ ip: f.ip || '', only_failed: f.only_failed ? 1 : 0,
            run_id: f.run_id || 0, limit: f.limit || 30 }).catch(function (err) { return { logs: [], load_error: '采集日志读取失败：' + err.message }; })
        ]).then(function (res) {
          var collectData = res[2] || {};
          collectData.last_logs = (res[3] || {}).logs || [];
          collectData.devices = collectData.devices || [];
          STATE.collect = collectData;
          STATE.collectDevices = collectData.devices;
          return Object.assign({}, res[0], {
            credentials: (res[1] || {}).credentials || [],
            credentials_error: (res[1] || {}).load_error || '',
            load_errors: res.slice(1).map(function (item) { return item.load_error; }).filter(Boolean),
            collect: collectData
          });
        });
      },
      render: pagePending, bind: bindPending
    },
    devices: {
      title: '设备台账',
      load: function () {
        var d = STATE.devices;
        return window.NetInspect.devices({
          keyword: d.keyword, type: d.type, status: d.status, vendor: d.vendor,
          group: d.group, region: d.region, online: d.online,
          name: d.name, role: d.role, model: d.model, version: d.version, ip: d.ip, owner: d.owner,
          location: d.location, asset_no: d.asset_no, usage: d.usage,
          warranty_until: d.warranty_until, note: d.note,
          page: d.page, page_size: d.page_size, sort: d.sort, order: d.order
        });
      },
      render: pageDevices, bind: bindDevices
    },
    server: {
      title: '服务器健康检查',
      load: function (query) { return window.NetInspect.healthServer(query.device || ''); },
      render: pageServer, bind: function (data) { bindHealth('server', 'svDevice', data); }
    },
    switch: {
      title: '交换机健康检查',
      load: function (query) { return window.NetInspect.healthSwitch(query.device || ''); },
      render: function (data) { return pageSwitch(data, 'switch'); },
      bind: function (data) { bindHealth('switch', 'swDevice', data); }
    },
    security: {
      title: '安全设备健康检查',
      load: function (query) { return window.NetInspect.healthSecurity(query.device || ''); },
      render: pageSecurity, bind: function (data) { bindHealth('security', 'swDevice', data); }
    },
    reports: {
      title: '巡检报告归档',
      load: function () {
        var r = STATE.reports;
        return Promise.all([
          window.NetInspect.archive({ keyword: r.keyword, kind: r.kind, fmt: r.fmt, device: r.device || '',
            page: r.page, page_size: r.page_size }),
          window.NetInspect.overview(STATE.days)
        ]).then(function (res) {
          return {
            archive: res[0], overview: res[1],
            source: res[1].source, source_info: res[1].source_info
          };
        });
      },
      render: pageReports, bind: bindReports
    },
    backup: {
      title: '配置备份',
      load: function () {
        var b = STATE.backup;
        return window.NetInspect.backups({ keyword: b.keyword, page: b.page,
                                           page_size: b.page_size });
      },
      render: pageBackup, bind: bindBackup
    },

    console: {
      title: '远程控制台',
      load: function () { return window.NetInspect.remoteOverview(); },
      render: pageRemote, bind: bindRemote
    },

    users: {
      title: '用户与权限',
      load: function () {
        var a = STATE.audit;
        return Promise.all([
          can('users') ? window.NetInspect.authUsers() : Promise.resolve({ users: [], roles: [] }),
          window.NetInspect.audit({
            hours: a.hours, username: a.username,
            action: a.action === 'all' ? '' : a.action,
            q: a.keyword, limit: 200
          }).catch(function (err) {
            return { available: false, error: err.message, rows: [], total: 0,
                     by_user: [], by_action: {}, action_labels: {} };
          })
        ]).then(function (res) {
          return { accounts: res[0], audit: res[1] };
        });
      },
      render: pageUsers, bind: bindUsers
    },
    settings: {
      title: '系统设置',
      load: function () {
        return Promise.all([
          window.NetInspect.status(),
          window.NetInspect.collectOverview(),
          window.NetInspect.diagnostics(),
          window.NetInspect.systemBackups()
        ]).then(function (res) {
          STATE.status = res[0];
          STATE.collect = res[1];
          return { status: res[0], collect: res[1],
                   diagnostics: res[2], backups: res[3] };
        });
      },
      render: pageSettings, bind: bindSettings
    },
    login: { title: '控制台入口', render: pageLogin, bind: bindLogin }
  };

  /* ---------- 构建版本同步：部署后已打开页面自动刷新 ---------- */
  function watchBuildVersion() {
    var meta = document.querySelector('meta[name="app-build"]');
    var current = meta ? (meta.getAttribute('content') || '') : '';
    if (!current) return;
    var checking = false;
    function check() {
      if (checking || document.hidden || !window.NetInspect) return;
      checking = true;
      fetch(window.NetInspect.base() + '/system/build', { cache: 'no-store' })
        .then(function (res) { return res.ok ? res.json() : null; })
        .then(function (data) {
          if (data && data.build && data.build !== current) window.location.reload();
        })
        .catch(function () {})
        .finally(function () { checking = false; });
    }
    window.setTimeout(check, 2500);
    window.setInterval(check, 30000);
    document.addEventListener('visibilitychange', function () { if (!document.hidden) check(); });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', watchBuildVersion, { once: true });
  } else {
    watchBuildVersion();
  }

  /* ---------- 路由 ---------- */
  var currentTheme = localStorage.getItem('na-theme') || 'dark';
  var routeToken = 0;
  var statusLoadedAt = 0;

  function applyTheme(t) {
    currentTheme = t;
    document.documentElement.setAttribute('data-theme', t);
    localStorage.setItem('na-theme', t);
    var b = document.getElementById('themeBtn');
    if (b) b.innerHTML = icon(t === 'light' ? 'moon' : 'sun', 18);
  }

  function parseQuery(text) {
    var out = {};
    (text || '').split('&').forEach(function (pair) {
      if (!pair) return;
      var kv = pair.split('=');
      out[decodeURIComponent(kv[0])] = decodeURIComponent(kv[1] || '');
    });
    return out;
  }

  function bindShell() {
    bindGlobalSearch();
    bindUserCard();
    var shell = document.querySelector('.app');
    var mobileBtn = document.getElementById('mobileNavBtn');
    var mobileBackdrop = document.getElementById('mobileNavBackdrop');
    function setMobileNav(open) {
      if (!shell) return;
      shell.classList.toggle('mobile-nav-open', !!open);
      if (mobileBtn) mobileBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    }
    if (mobileBtn) mobileBtn.addEventListener('click', function () { setMobileNav(!shell.classList.contains('mobile-nav-open')); });
    if (mobileBackdrop) mobileBackdrop.addEventListener('click', function () { setMobileNav(false); });
    Array.prototype.forEach.call(document.querySelectorAll('.sidebar a.nav-item'), function (link) {
      link.addEventListener('click', function () { setMobileNav(false); });
    });
    if (!document.documentElement.dataset.mobileNavResizeBound) {
      document.documentElement.dataset.mobileNavResizeBound = '1';
      window.addEventListener('resize', function () {
        if (window.innerWidth > 900) {
          var current = document.querySelector('.app');
          if (current) current.classList.remove('mobile-nav-open');
          var btn = document.getElementById('mobileNavBtn');
          if (btn) btn.setAttribute('aria-expanded', 'false');
        }
      }, { passive: true });
      document.addEventListener('keydown', function (event) {
        if (event.key !== 'Escape') return;
        var current = document.querySelector('.app');
        if (!current || !current.classList.contains('mobile-nav-open')) return;
        current.classList.remove('mobile-nav-open');
        var btn = document.getElementById('mobileNavBtn');
        if (btn) btn.setAttribute('aria-expanded', 'false');
      });
    }
    var tb = document.getElementById('themeBtn');
    if (tb) {
      tb.innerHTML = icon(currentTheme === 'light' ? 'moon' : 'sun', 18);
      tb.addEventListener('click', function () {
        applyTheme(currentTheme === 'light' ? 'dark' : 'light');
      });
    }
  }

  function ensureStatus(force) {
    if (!window.NetInspect.token()) return;          // 未登录：不必探活
    if (!force && STATE.status && (Date.now() - statusLoadedAt) < 20000) return;
    statusLoadedAt = Date.now();
    window.NetInspect.status().then(function (st) {
      STATE.status = st;
      paintSourceBadges();
    }).catch(function () {
      STATE.status = STATE.status || { source: 'local', source_label: '本平台自带采集', counts: {} };
      paintSourceBadges();
    });
  }

  function route() {
    var raw = (location.hash || '#/overview').replace(/^#\/?/, '');
    var parts = raw.split('?');
    var key = parts[0] || 'overview';
    var query = parseQuery(parts[1]);
    if (key === 'collect') {
      location.hash = '#/pending';
      return;
    }
    var PAGE_ALIASES = { remote: 'console', templates: 'reports' };
    if (PAGE_ALIASES[key]) {
      location.hash = '#/' + PAGE_ALIASES[key] + (parts[1] ? '?' + parts[1] : '');
      return;
    }
    if (!PAGES[key]) key = 'overview';
    var previousMain = document.getElementById('main');
    var preserveScroll = STATE.lastRenderedPage === key && previousMain ? previousMain.scrollTop : 0;
    if (STATE.wallTimers) {
      STATE.wallTimers.forEach(function (t) { try { t.stop(); } catch (e) {} });
      STATE.wallTimers = null;
    }
    document.body.classList.toggle('wall-mode', key === 'wall');
    var page = PAGES[key];
    var token = ++routeToken;

    // 会话引导：第一次进来先问后端「我是谁」
    if (!STATE.authReady) {
      document.body.innerHTML = '<div id="app"></div>';
      document.getElementById('app').innerHTML = loadingView('正在校验登录状态');
      return bootstrapAuth().then(function () { route(); });
    }
    if (key === 'login') {
      if (STATE.user) {                       // 已登录就别停在登录页
        var target = STATE.nextHash || '#/overview';
        STATE.nextHash = '';
        location.hash = target;
        return;
      }
      if (!STATE.authStatus) {
        window.NetInspect.authStatus().then(function (st) {
          STATE.authStatus = st;
          // 拉状态是异步的：期间可能已经登录成功，那就别再刷回登录页
          if (!STATE.user && key_href() === 'login') renderLogin();
        });
      }
      renderLogin();
      return;
    }
    if (!STATE.user) {                        // 没登录：记住想去哪，转登录页
      STATE.nextHash = location.hash && location.hash !== '#/login' ? location.hash : '';
      location.hash = '#/login';
      return;
    }

    syncStateFromQuery(key, query);

    document.body.innerHTML = '<div class="app">' +
      '<button type="button" class="mobile-nav-backdrop" id="mobileNavBackdrop" aria-label="关闭导航"></button>' +
      '<aside class="sidebar" id="sidebar"></aside>' +
      '<main class="main' + (key === 'users' ? ' compact' : '') + '" id="main"></main></div>';
    document.getElementById('sidebar').innerHTML = renderNav(key);
    var main = document.getElementById('main');
    main.setAttribute('data-page', key);
    main.innerHTML = loadingView(page.title);
    document.title = siteParts().name;
    paintSourceBadges();
    bindShell();
    ensureStatus(false);

    page.load(query).then(function (data) {
      if (token !== routeToken) return;
      main.innerHTML = page.render(data);
      mountWorkflow(main, key, query, data);
      paintSourceBadges();
      bindShell();
      if (page.bind) page.bind(data, query);
      main.scrollTop = preserveScroll;
      STATE.lastRenderedPage = key;
    }).catch(function (err) {
      if (token !== routeToken) return;
      main.innerHTML = topbar() + '<div class="page-head"><div class="page-title"><h1>' + esc(page.title) + '</h1></div></div>' + errorView(err);
      bindShell();
      var retry = document.getElementById('retryLoad');
      if (retry) retry.addEventListener('click', route);
      showToast('加载失败：' + err.message);
    });
  }

  /* ---------- 全局事件 ---------- */
  document.addEventListener('keydown', function (e) {
    if (OPEN_SELECT) {
      if (e.key === 'Escape') { e.preventDefault(); closeSelect(); return; }
      if (e.key === 'ArrowDown') { e.preventDefault(); moveSelect(1); return; }
      if (e.key === 'ArrowUp') { e.preventDefault(); moveSelect(-1); return; }
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        var options = selectOptions(OPEN_SELECT);
        if (options[SELECT_INDEX]) chooseSelect(OPEN_SELECT, options[SELECT_INDEX].value);
        return;
      }
      if (e.key === 'Tab') closeSelect();
    }
    if (e.key === 'Escape') {
      Array.prototype.forEach.call(document.querySelectorAll('.workflow[open],.health-export[open]'), function (menu) { menu.removeAttribute('open'); });
      dismissOverlay();
    }
  });

  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!t) return;
    if (!t.closest || !t.closest('.workflow,.health-export')) {
      Array.prototype.forEach.call(document.querySelectorAll('.workflow[open]'), function (menu) { menu.removeAttribute('open'); });
    }

    var trigger = t.closest && t.closest('[data-open]');
    if (trigger) {
      e.preventDefault();
      var sid = trigger.getAttribute('data-open');
      if (OPEN_SELECT === sid) { closeSelect(); } else { openSelect(sid); }
      return;
    }
    if (t.closest && t.closest('#naPanel')) return;
    if (OPEN_SELECT) closeSelect();

    var closer = t.closest && t.closest('[data-close]');
    if (closer) { e.preventDefault(); dismissOverlay(); return; }
    var cancelBtn = t.closest && t.closest('[data-overlay-cancel]');
    if (cancelBtn) { e.preventDefault(); dismissOverlay(); return; }
    var iconClose = t.closest && t.closest('#overlay .icon-btn');
    if (iconClose) { e.preventDefault(); dismissOverlay(); return; }
    if (t.closest && t.closest('#mdClose,#mdCancel,#dwClose,#dwCancel,#cfCancel,#cfOk,#cfClose,#lgClose,#lgCancel,#crClose,#crCancel,#plClose,#plCancel,#seClose,#seCancel,#acClose,#acCancel,#se2Close,#se2Cancel,#umClose,#umCancel,#rpClose2,#rsCancel,#liClose,#liCancel,#devClose,#devCancel,#diClose,#diCancel,#csClose,#csCancel,#ldClose,#ldCancel')) {
      dismissOverlay();
      return;
    }
    var perm = t.closest && t.closest('[data-perm]');
    if (perm) {
      var on = perm.classList.contains('on');
      perm.classList.remove('on', 'partial');
      perm.classList.add(on ? 'partial' : 'on');
      perm.innerHTML = on ? '' : icon('check', 10);
      return;
    }
    var sw = t.closest && t.closest('[data-toggle]');
    if (sw) {
      var state = sw.classList.contains('on');
      sw.classList.toggle('on', !state);
      sw.classList.toggle('off', state);
      sw.setAttribute('aria-pressed', String(!state));
    }
  });

  window.NetInspect.onUnauthorized(function () {
    var onLoginPage = key_href() === 'login';
    STATE.user = null;
    STATE.perms = {};
    STATE.authReady = true;
    closeOverlay();
    if (!onLoginPage) {                       // 已在登录页就别再刷（避免把「本来想去的页面」冲掉）
      STATE.nextHash = location.hash && location.hash !== '#/login' ? location.hash : '';
      renderLogin('登录状态已失效，请重新登录', 'danger');
      stateLogoutHint();
    }
  });

  window.addEventListener('beforeunload', function () {
    try { localStorage.setItem('ni-last-user', STATE.lastUser || ''); } catch (e) {}
  });

  function stateLogoutHint() {
    try { localStorage.setItem('ni-last-user', ''); } catch (e) {}
  }

  // 页面/弹窗滚动时：面板自己滚不动它，其它滚动让它跟着触发器走，触发器滚出视口才收起
  window.addEventListener('scroll', function (event) {
    if (!OPEN_SELECT) return;
    var panel = document.getElementById('naPanel');
    var target = event.target;
    if (panel && target && (target === panel || (target.contains && target.contains(panel)))) return;
    if (panel && target && panel.contains && panel.contains(target)) return;   // 滚的是列表面板
    if (!positionSelectPanel()) closeSelect();
  }, true);
  // 滚轮落在面板里：只滚列表，不带动页面（否则页面一动面板就飘）
  window.addEventListener('wheel', function (event) {
    if (!OPEN_SELECT) return;
    var panel = document.getElementById('naPanel');
    if (panel && panel.contains(event.target)) { event.stopPropagation(); }
  }, { passive: true, capture: true });
  window.addEventListener('resize', function () { if (OPEN_SELECT) closeSelect(); });

  applyTheme(currentTheme);
  window.addEventListener('hashchange', route);

  window.NetInspect.branding().then(function (brand) {
    STATE.meta = Object.assign({}, STATE.meta || {}, brand || {});
    if (brand && brand.period_days && !STATE.user) STATE.days = Number(brand.period_days) || STATE.days;
    if (!window.NetInspect.token() && !STATE.user && location.hash) route();
  }).catch(function () { /* 登录前品牌取不到也不影响页面 */ });

  if (window.NetInspect.token()) window.NetInspect.meta().then(function (meta) {
    STATE.meta = Object.assign({}, STATE.meta || {}, meta || {});
    if (meta.period_days) STATE.days = Number(meta.period_days) || STATE.days;
    if (location.hash) route();
  }).catch(function () { /* 元数据取不到也不影响页面 */ });

  route();
})();









































