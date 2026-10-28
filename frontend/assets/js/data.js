/* Navigation only. Business data, account state and policies come from the API. */
window.NAV = [
  {
    "key": "monitor",
    "group": "态势与告警",
    "icon": "gauge",
    "items": [
      {
        "key": "overview",
        "label": "巡检总览",
        "icon": "gauge"
      },
      {
        "key": "wall",
        "label": "巡检大屏",
        "icon": "monitor"
      },
      {
        "key": "alerts",
        "label": "告警中心",
        "icon": "alert"
      },
      {
        "key": "search",
        "label": "全局检索",
        "icon": "search"
      }
    ]
  },
  {
    "key": "assets",
    "group": "资产与运维",
    "icon": "server",
    "items": [
      {
        "key": "pending",
        "label": "设备采集",
        "icon": "refresh"
      },
      {
        "key": "devices",
        "label": "设备台账",
        "icon": "server"
      },
      {
        "key": "backup",
        "label": "配置备份",
        "icon": "archive"
      },
      {
        "key": "console",
        "label": "远程控制台",
        "icon": "terminal"
      }
    ]
  },
  {
    "key": "health",
    "group": "健康与报告",
    "icon": "cpu",
    "items": [
      {
        "key": "switch",
        "label": "交换机健康检查",
        "icon": "network"
      },
      {
        "key": "server",
        "label": "服务器健康检查",
        "icon": "cpu"
      },
      {
        "key": "security",
        "label": "安全设备健康检查",
        "icon": "lock"
      },
      {
        "key": "reports",
        "label": "巡检报告归档",
        "icon": "file"
      }
    ]
  },
  {
    "key": "system",
    "group": "系统管理",
    "icon": "settings",
    "items": [
      {
        "key": "users",
        "label": "用户、权限与审计",
        "icon": "users"
      },
      {
        "key": "settings",
        "label": "系统设置",
        "icon": "settings"
      }
    ]
  }
];
