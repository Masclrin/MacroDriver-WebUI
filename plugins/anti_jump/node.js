var nodes = {
  'plugin/anti_jump': {
    display_name: '防跳秒',
    color: '#f59e0b',
    category: 'plugin',
    icon: 'fa-solid fa-clock',
    backendAction: 'anti_jump',
    inputs: [{name:'in', type:'flow'}],
    outputs: [
      {name:'next', type:'flow'},
      {name:'timeout', type:'flow'},
      {name:'trigger_count', type:'data'}
    ],
    params_schema: {
      stop_mode: {
        type: 'bool', label: '停止信号', default: false,
        description: '开启后本节点变为停止信号，设置控制变量通知同流程中的防跳秒节点退出'
      },

      mode: {
        type: 'enum', label: '坐标模式', default: 'relative',
        options: ['screen', 'window', 'relative'], coordMode: true,
        description: 'screen=屏幕绝对坐标, window=窗口内坐标, relative=窗口内比例坐标(0~1)',
        showWhen: 'stop_mode=false'
      },
      hwnd_var: {
        type: 'string', label: '窗口变量', default: '', varRef: true,
        description: 'window/relative模式需要指定窗口句柄变量名',
        showWhen: 'stop_mode=false'
      },

      combo_count: {
        type: 'number', label: '动作组合数', default: 1, min: 0, max: 5,
        description: '0=纯黑屏监听模式，无需按键触发',
        showWhen: 'stop_mode=false'
      },
      combo_time_window: {
        type: 'number', label: '组合时间窗口(秒)', default: 2.0, min: 0.1, max: 10, step: 0.1,
        description: '按键与点击的时间窗口',
        showWhen: 'stop_mode=false,combo_count>=1'
      },

      combo_0_keys: {
        type: 'string', label: '组合1-按键', default: 'esc',
        description: '逗号分隔多个键，如 esc 或 ctrl+shift+a',
        showWhen: 'stop_mode=false,combo_count>=1'
      },
      combo_0_region: {
        type: 'region', label: '组合1-点击区域', default: [0.468,0.464,0.064,0.037], coordMode: true,
        description: '默认监听键盘按键+鼠标左键点击，留空[0,0,0,0]表示仅按键触发',
        showWhen: 'stop_mode=false,combo_count>=1'
      },
      combo_1_keys: {
        type: 'string', label: '组合2-按键', default: '',
        showWhen: 'stop_mode=false,combo_count>=2'
      },
      combo_1_region: {
        type: 'region', label: '组合2-点击区域', default: [0,0,0,0], coordMode: true,
        showWhen: 'stop_mode=false,combo_count>=2'
      },
      combo_2_keys: {
        type: 'string', label: '组合3-按键', default: '',
        showWhen: 'stop_mode=false,combo_count>=3'
      },
      combo_2_region: {
        type: 'region', label: '组合3-点击区域', default: [0,0,0,0], coordMode: true,
        showWhen: 'stop_mode=false,combo_count>=3'
      },
      combo_3_keys: {
        type: 'string', label: '组合4-按键', default: '',
        showWhen: 'stop_mode=false,combo_count>=4'
      },
      combo_3_region: {
        type: 'region', label: '组合4-点击区域', default: [0,0,0,0], coordMode: true,
        showWhen: 'stop_mode=false,combo_count>=4'
      },
      combo_4_keys: {
        type: 'string', label: '组合5-按键', default: '',
        showWhen: 'stop_mode=false,combo_count>=5'
      },
      combo_4_region: {
        type: 'region', label: '组合5-点击区域', default: [0,0,0,0], coordMode: true,
        showWhen: 'stop_mode=false,combo_count>=5'
      },

      black_region: {
        type: 'region', label: '黑屏检测区域', default: [0.01,0.096,0.022,0.037], coordMode: true,
        description: '框选黑屏检测位置 ，切换模式后需重新框选',
        showWhen: 'stop_mode=false'
      },
      black_thresh: {
        type: 'number', label: '黑屏亮度阈值', default: 60, min: 0, max: 255,
        description: '低于此值视为暗像素',
        showWhen: 'stop_mode=false'
      },
      black_ratio: {
        type: 'number', label: '黑屏暗像素比例', default: 0.9, min: 0, max: 1, step: 0.05,
        showWhen: 'stop_mode=false'
      },
      black_timeout: {
        type: 'number', label: '黑屏检测超时(秒)', default: 2.0, min: 0.1, max: 30, step: 0.1,
        showWhen: 'stop_mode=false'
      },

      bright_region: {
        type: 'region', label: '亮屏检测区域', default: [0.583,0.928,0.003,0.008], coordMode: true,
        description: '框选亮屏检测位置 (默认基于1920x1080)，切换模式后需重新框选',
        showWhen: 'stop_mode=false'
      },
      bright_thresh: {
        type: 'number', label: '亮屏亮度阈值', default: 80, min: 0, max: 255,
        description: '高于此值视为亮像素',
        showWhen: 'stop_mode=false'
      },
      bright_ratio: {
        type: 'number', label: '亮屏亮像素比例', default: 0.5, min: 0, max: 1, step: 0.05,
        showWhen: 'stop_mode=false'
      },
      bright_timeout: {
        type: 'number', label: '亮屏检测超时(秒)', default: 8.0, min: 0.1, max: 60, step: 0.5,
        showWhen: 'stop_mode=false'
      },

      wait_before_lock: {
        type: 'number', label: '锁帧前等待(秒)', default: 0.2, min: 0, max: 10, step: 0.1,
        showWhen: 'stop_mode=false'
      },
      wait_after_lock: {
        type: 'number', label: '锁帧后等待(秒)', default: 1.5, min: 0, max: 10, step: 0.1,
        showWhen: 'stop_mode=false'
      },
      wait_after_bright: {
        type: 'number', label: '亮屏后等待(秒)', default: 0.3, min: 0, max: 10, step: 0.1,
        showWhen: 'stop_mode=false'
      },
      cooldown_after_cycle: {
        type: 'number', label: '周期冷却(秒)', default: 1.0, min: 0, max: 10, step: 0.1,
        description: '恢复帧率后的冷却期，期间忽略新的黑屏触发，防止画面闪烁导致重复锁帧',
        showWhen: 'stop_mode=false'
      },

      rtss_hotkey: {
        type: 'string', label: 'RTSS快捷键', default: 'f6',
        description: '触发RTSS锁帧/恢复帧率的快捷键',
        showWhen: 'stop_mode=false'
      },

      idle_timeout: {
        type: 'number', label: '无触发超时(秒)', default: 0, min: 0, max: 3600, step: 1,
        description: '0=不限制，超过此时间无触发走超时出口',
        showWhen: 'stop_mode=false'
      },
      max_count: {
        type: 'number', label: '最大执行次数', default: 0, min: 0, max: 9999, step: 1,
        description: '0=不限制，达到后走next出口',
        showWhen: 'stop_mode=false'
      },
      control_var: {
        type: 'string', label: '控制变量名', default: 'anti_jump_control',
        description: '其他防跳秒节点(停止模式)通过此变量名发送停止信号',
        showWhen: 'stop_mode=false'
      },

      control_var_stop: {
        type: 'string', label: '控制变量名', default: 'anti_jump_control',
        description: '设置此变量的值为"stop"，通知同名的防跳秒监听节点退出',
        showWhen: 'stop_mode=true'
      }
    }
  }
};
window.__plugin_nodes__ = nodes;