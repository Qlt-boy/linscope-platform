/* ============ 林鉴知微平台 | LinScopePlatform · 后端接口客户端 ============
 *
 * 页面不再使用写死的数据：全部改由这里向后端 FastAPI 取数。
 * 后端从本平台自己的采集库（SQLite）取数并归一化。
 *
 * 接口地址解析顺序：
 *   1. URL 参数 ?api=https://host:1314/api     （临时指向别的后端）
 *   2. localStorage 的 ni-api-base            （页面里改过就记住）
 *   3. 与页面同源（后端直接托管了前端，走 /api）
 *   4. file:// 直接打开时，默认 https://127.0.0.1:1314/api
 */
window.NetInspect = (function () {
  'use strict';

  var LS_KEY = 'ni-api-base';

  function resolveBase() {
    var fromQuery = (location.search.match(/[?&]api=([^&]+)/) || [])[1];
    if (fromQuery) {
      var value = decodeURIComponent(fromQuery).replace(/\/+$/, '');
      try { localStorage.setItem(LS_KEY, value); } catch (e) {}
      return value;
    }
    var saved = '';
    try { saved = localStorage.getItem(LS_KEY) || ''; } catch (e) {}
    if (saved) return saved.replace(/\/+$/, '');
    if (location.protocol === 'http:' || location.protocol === 'https:') {
      return location.origin + '/api';
    }
    return 'https://127.0.0.1:1314/api';
  }

  var BASE = resolveBase();
  var TOKEN_KEY = 'ni-token';

  function token() {
    try { return localStorage.getItem(TOKEN_KEY) || ''; } catch (e) { return ''; }
  }

  function setToken(value) {
    try {
      if (value) { localStorage.setItem(TOKEN_KEY, value); }
      else { localStorage.removeItem(TOKEN_KEY); }
    } catch (e) {}
  }

  var onUnauthorized = null;

  function setBase(value) {
    BASE = String(value || '').replace(/\/+$/, '');
    try { localStorage.setItem(LS_KEY, BASE); } catch (e) {}
  }

  function query(params) {
    var parts = [];
    Object.keys(params || {}).forEach(function (k) {
      var v = params[k];
      if (v === undefined || v === null || v === '') return;
      parts.push(encodeURIComponent(k) + '=' + encodeURIComponent(v));
    });
    return parts.length ? '?' + parts.join('&') : '';
  }

  function request(path, options) {
    options = options || {};
    var url = BASE + path + query(options.params);
    var init = { method: options.method || 'GET', headers: {} };
    if (options.body !== undefined) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(options.body);
    }
    var session = token();
    if (session && !options.anonymous) {
      init.headers['Authorization'] = 'Bearer ' + session;
    }
    return fetch(url, init).then(function (resp) {
      return resp.text().then(function (text) {
        var payload = null;
        try { payload = text ? JSON.parse(text) : null; } catch (e) { payload = null; }
        if (!resp.ok) {
          var message = (payload && (payload.error || payload.detail)) || text ||
            ('HTTP ' + resp.status);
          var err = new Error(typeof message === 'string' ? message : '请求失败');
          err.status = resp.status;
          if (resp.status === 401 && !options.anonymous) {
            err.unauthorized = true;
            setToken('');
            if (onUnauthorized) { onUnauthorized(err); }
          }
          err.payload = payload;
          err.url = url;
          throw err;
        }
        return payload;
      });
    }, function (netErr) {
      var err = new Error('无法连接后端接口（' + BASE + '）：' + netErr.message);
      err.offline = true;
      err.url = url;
      throw err;
    });
  }

  function binaryRequest(path, data, options) {
    options = options || {};
    var url = BASE + path + query(options.params);
    var init = {
      method: options.method || 'POST',
      headers: {
        'Authorization': 'Bearer ' + token(),
        'Content-Type': 'application/octet-stream'
      },
      body: data
    };
    return fetch(url, init).then(function (resp) {
      return resp.text().then(function (text) {
        var payload = null;
        try { payload = text ? JSON.parse(text) : null; } catch (e) { payload = null; }
        if (!resp.ok) {
          var message = (payload && (payload.error || payload.detail)) || text || ('HTTP ' + resp.status);
          var err = new Error(message);
          err.status = resp.status;
          throw err;
        }
        return payload || { ok: true };
      });
    });
  }
  return {
    base: function () { return BASE; },
    setBase: setBase,
    request: request,
    token: token,
    setToken: setToken,
    onUnauthorized: function (handler) { onUnauthorized = handler; },

    /* ---- 账号：登录 / 退出 / 口令 / 会话 / 账号管理 / 登录审计 ---- */
    authStatus: function () { return request('/auth/status', { anonymous: true }); },
    login: function (username, password, remember) {
      return request('/auth/login', { method: 'POST', anonymous: true,
        body: { username: username, password: password, remember: !!remember } });
    },
    logout: function () { return request('/auth/logout', { method: 'POST' }); },
    me: function () { return request('/auth/me'); },
    changePassword: function (oldPassword, newPassword) {
      return request('/auth/password', { method: 'POST',
        body: { old_password: oldPassword, new_password: newPassword } });
    },
    authSessions: function (all) {
      return request('/auth/sessions', { params: all ? { all: '1' } : {} });
    },
    revokeSession: function (hint) {
      return request('/auth/sessions/' + encodeURIComponent(hint), { method: 'DELETE' });
    },
    authEvents: function (params) { return request('/auth/events', { params: params }); },
    authUsers: function () { return request('/auth/users'); },
    createUser: function (body) { return request('/auth/users', { method: 'POST', body: body }); },
    updateUser: function (id, body) {
      return request('/auth/users/' + id, { method: 'PUT', body: body });
    },
    resetUserPassword: function (id, password) {
      return request('/auth/users/' + id + '/password', { method: 'POST', body: { password: password } });
    },
    deleteUser: function (id) { return request('/auth/users/' + id, { method: 'DELETE' }); },

    /* ---- 系统 / 数据源 ---- */
    status: function () { return request('/system/status'); },
    diagnostics: function () { return request('/system/diagnostics'); },
    systemBackups: function () { return request('/system/backups'); },
    runSystemBackup: function () { return request('/system/backups/run', { method: 'POST', body: {} }); },
    systemBackupDownloadUrl: function (name) {
      return BASE + '/system/backups/download' + query({ name: name });
    },
    meta: function () { return request('/system/meta'); },
    branding: function () { return request('/system/branding', { anonymous: true }); },
    saveSettings: function (body) {
      return request('/system/settings', { method: 'POST', body: body });
    },

    /* ---- 总览 / 设备 / 健康检查 ---- */
    overview: function (days) {
      return request('/dashboard/overview', { params: { days: days || 7 } });
    },
    resources: function (days) {
      return request('/dashboard/resources', { params: { days: days || 7 } });
    },
    wall: function () { return request('/dashboard/wall'); },
    packageBackupsUrl: function (device) {
      return BASE + '/backups/package' + (device ? query({ device: device }) : '');
    },
    devices: function (params) { return request('/devices', { params: params }); },
    device: function (key) { return request('/devices/' + encodeURIComponent(key)); },
    saveLedger: function (key, body) {
      return request('/devices/' + encodeURIComponent(key) + '/ledger',
        { method: 'PUT', body: body });
    },
    healthServer: function (device) {
      return request('/health/server', { params: { device: device } });
    },
    healthSwitch: function (device) {
      return request('/health/switch', { params: { device: device } });
    },
    healthSecurity: function (device) {
      return request('/health/security', { params: { device: device } });
    },
    alerts: function (params) { return request('/alerts', { params: params }); },
    disposeAlerts: function (ids, status, assignee, note) {
      return request('/alerts/disposition', { method: 'POST',
        body: { ids: ids || [], status: status, assignee: assignee || '', note: note || '' } });
    },
    inspections: function (params) { return request('/inspections', { params: params }); },
    backups: function (params) { return request('/backups', { params: params }); },

    /* ---- 全局搜索 / 审计 / 账号 / 模板 / 台账 ---- */
    search: function (q, limit) {
      return request('/search', { params: { q: q, limit: Math.max(1, Math.min(50, Math.floor(Number(limit) || 8))) } });
    },
    audit: function (params) { return request('/audit', { params: params }); },
    users: function (params) { return request('/users', { params: params }); },
    /* /api/users 已经把令牌身份与审计一起返回，页面不必再单独打 /audit */
    templates: function () { return request('/templates'); },
    ledger: function () { return request('/ledger'); },
    ledgerImport: function (csv, dryRun, clearEmpty) {
      return request('/ledger/import', { method: 'POST',
        body: { csv: csv, dry_run: !!dryRun, clear_empty: !!clearEmpty } });
    },

    /* ---- 自带采集（华为 VRP） ---- */
    collectOverview: function (params) { return request('/collect/overview', { params: params || {} }); },
    collectSettings: function () { return request('/collect/settings'); },
    saveCollectSettings: function (body) {
      return request('/collect/settings', { method: 'POST', body: body });
    },
    collectRun: function (body) { return request('/collect/run', { method: 'POST', body: body || {} }); },
    collectRuns: function () { return request('/collect/runs'); },
    collectLogs: function (params) {
      return request('/collect/logs', { params: params || {} });
    },
    collectLog: function (id) { return request('/collect/logs/' + id); },
    collectPrecheck: function (ips, timeout) {
      return request('/collect/precheck', { method: 'POST',
        body: { ips: ips || null, timeout: timeout || 2.5 } });
    },
    collectLogsCsvUrl: function (params) {
      return BASE + '/collect/logs/export.csv' + query(params || {});
    },
    collectPurge: function (keepDays) {
      return request('/collect/purge', { method: 'POST', body: { keep_days: keepDays || 30 } });
    },
    createDevice: function (body) { return request('/devices', { method: 'POST', body: body }); },
    updateDevice: function (ip, body) {
      return request('/devices/' + encodeURIComponent(ip), { method: 'PUT', body: body });
    },
    deleteDevice: function (ip, purgeHistory) {
      return request('/devices/' + encodeURIComponent(ip), {
        method: 'DELETE', params: { purge_history: purgeHistory === false ? 0 : 1 }
      });
    },
    demoDeviceCandidates: function () { return request('/devices/demo-candidates'); },
    purgeDemoDevices: function (ips, purgeHistory) {
      return request('/devices/purge-demo', { method: 'POST',
        body: { ips: ips || [], purge_history: purgeHistory !== false,
                confirm: 'PURGE_DEMO' } });
    },
    importDevices: function (csv, dryRun) {
      return request('/devices/import', { method: 'POST', body: { csv: csv, dry_run: !!dryRun } });
    },

    /* ---- 远程登录（SSH 控制台） ---- */
    remoteOverview: function () { return request('/remote/overview'); },
    remoteCredentials: function () { return request('/remote/credentials'); },
    remoteCredential: function (ip) { return request('/remote/credentials/' + encodeURIComponent(ip)); },
    saveCredential: function (ip, body) {
      return request('/remote/credentials/' + encodeURIComponent(ip), { method: 'PUT', body: body });
    },
    deleteCredential: function (ip) {
      return request('/remote/credentials/' + encodeURIComponent(ip), { method: 'DELETE' });
    },
    remoteTest: function (ip, body) { return request('/remote/test', { method: 'POST', body: Object.assign({ ip: ip }, body || {}) }); },
    remotePolicy: function () { return request('/remote/policy'); },
    saveRemotePolicy: function (body) { return request('/remote/policy', { method: 'POST', body: body }); },
    checkRemoteCommand: function (command) {
      return request('/remote/check', { method: 'POST', body: { command: command } });
    },
    remoteSessions: function (params) { return request('/remote/sessions', { params: params }); },
    remoteCommands: function (id) {
      return request('/remote/sessions/' + id + '/commands');
    },
    remoteStats: function () { return request('/remote/stats'); },
    remoteSftpList: function (ip, path) {
      return request('/remote/sftp/list', { params: { ip: ip, path: path || '' } });
    },
    remoteSftpDownloadUrl: function (ip, path) {
      return BASE + '/remote/sftp/download' + query({ ip: ip, path: path });
    },
    remoteSftpUpload: function (ip, path, name, buffer) {
      return binaryRequest('/remote/sftp/upload', buffer,
        { params: { ip: ip, path: path || '.', name: name } });
    },
    remoteSftpMkdir: function (ip, path, name) {
      return request('/remote/sftp/mkdir', { method: 'POST', body: { ip: ip, path: path, name: name } });
    },
    remoteSftpRename: function (ip, path, newName) {
      return request('/remote/sftp/rename', { method: 'POST', body: { ip: ip, path: path, new_name: newName } });
    },
    remoteSftpDelete: function (ip, path) {
      return request('/remote/sftp/item', { method: 'DELETE', params: { ip: ip, path: path } });
    },
    resetRemoteHostKey: function (ip) {
      return request('/remote/host-key/' + encodeURIComponent(ip) + '/reset', { method: 'POST', body: {} });
    },

    /** WebSocket 地址（http→ws / https→wss，同源 + /api） */
    wsUrl: function (path) {
      var root = BASE.replace(/\/api$/, '').replace(/^http/, 'ws');
      var session = token();
      var sep = path.indexOf('?') >= 0 ? '&' : '?';
      // 浏览器 WebSocket 不能带自定义头，令牌用查询串带过去（后端校验后立即用于鉴权）
      return root + '/api' + path + (session ? sep + 'token=' + encodeURIComponent(session) : '');
    },

    /* ---- 报表 ---- */
    archive: function (params) { return request('/reports/archive', { params: params }); },
    legacyTemplates: function () { return request('/reports/templates'); },
    exportUrl: function (params) {
      return BASE + '/reports/export' + query(params);
    },
    reExportUrl: function (id, format) {
      return BASE + '/reports/export/' + id + query({ format: format });
    },
    removeArchive: function (id) {
      return request('/reports/archive/' + id, { method: 'DELETE' });
    }
  };
})();


