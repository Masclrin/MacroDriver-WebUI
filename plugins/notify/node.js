var _notifyHelper = {
  _playSound: function(soundType, customFile) {
    if (soundType === 'none') return;
    if (customFile) {
      try { var audio = new Audio(customFile); audio.volume = 0.5; audio.play().catch(function() {}); return; } catch(e) {}
    }
    try {
      var ctx = new (window.AudioContext || window.webkitAudioContext)();
      var t = ctx.currentTime;
      var master = ctx.createGain();
      master.connect(ctx.destination);
      master.gain.value = 0.2;
      var configs = {
        'default': [{f:800,t:'sine',d:0.12,delay:0}],
        'info': [{f:520,t:'sine',d:0.10,delay:0},{f:680,t:'sine',d:0.14,delay:0.08}],
        'success': [{f:523,t:'sine',d:0.10,delay:0},{f:659,t:'sine',d:0.10,delay:0.10},{f:784,t:'sine',d:0.18,delay:0.20}],
        'warning': [{f:440,t:'triangle',d:0.15,delay:0},{f:370,t:'triangle',d:0.25,delay:0.12}],
        'error': [{f:300,t:'sawtooth',d:0.18,delay:0},{f:260,t:'sawtooth',d:0.28,delay:0.12}],
      };
      var seq = configs[soundType] || configs['default'];
      seq.forEach(function(cfg) {
        var osc = ctx.createOscillator();
        var g = ctx.createGain();
        osc.type = cfg.t;
        osc.frequency.value = cfg.f;
        g.gain.setValueAtTime(0.001, t + cfg.delay);
        g.gain.exponentialRampToValueAtTime(1, t + cfg.delay + 0.015);
        g.gain.exponentialRampToValueAtTime(0.001, t + cfg.delay + cfg.d);
        osc.connect(g); g.connect(master);
        osc.start(t + cfg.delay); osc.stop(t + cfg.delay + cfg.d);
      });
    } catch(e) {}
  },

  _speak: function(text, volume, rate, voiceName) {
    if (!text || !window.speechSynthesis) return;
    var utt = new SpeechSynthesisUtterance(text);
    utt.volume = Math.max(0, Math.min(1, parseFloat(volume) || 0.8));
    utt.rate = Math.max(0.5, Math.min(2, parseFloat(rate) || 1.0));
    utt.lang = 'zh-CN';
    // 按名称匹配用户指定的语音
    if (voiceName) {
      var voices = window.speechSynthesis.getVoices();
      var found = voices.find(function(v) {
        return v.name.toLowerCase().indexOf(voiceName.toLowerCase()) !== -1;
      });
      if (found) utt.voice = found;
    }
    window.speechSynthesis.speak(utt);
  },

  _showPopup: function(data) {
    var title = data.title || '提示';
    var message = data.message || '';
    var sound = data.sound || 'default';
    var duration = data.duration || 3000;
    var position = data.position || 'bottom-right';
    var customSound = data.custom_sound || '';
    var fontSize = data.font_size || 12;

    this._playSound(sound, customSound);

    var container = document.getElementById('notify-popup-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'notify-popup-container';
      document.body.appendChild(container);
    }
    var posStyle = '';
    if (position === 'bottom-right') posStyle = 'bottom:20px;right:20px;align-items:flex-end;';
    else if (position === 'bottom-left') posStyle = 'bottom:20px;left:20px;align-items:flex-start;';
    else if (position === 'top-right') posStyle = 'top:20px;right:20px;align-items:flex-end;';
    else if (position === 'top-left') posStyle = 'top:20px;left:20px;align-items:flex-start;';
    else posStyle = 'top:50%;left:50%;transform:translate(-50%,-50%);align-items:center;';
    container.setAttribute('style', 'position:fixed;z-index:99999;pointer-events:none;display:flex;flex-direction:column;gap:8px;' + posStyle);

    var colorMap = {
      'default':'#3b82f6','info':'#06b6d4','success':'#22c55e','warning':'#eab308','error':'#ef4444'
    };
    var borderColor = colorMap[sound] || '#3b82f6';

    var popup = document.createElement('div');
    popup.style.cssText = 'pointer-events:auto;min-width:280px;max-width:400px;background:var(--bg,#1e1e2e);border:1px solid '
      + borderColor + ';border-radius:10px;box-shadow:0 8px 32px rgba(0,0,0,.5);opacity:0;transform:translateY(12px);transition:all .35s cubic-bezier(.4,0,.2,1);font-family:system-ui,sans-serif;overflow:hidden;';

    popup.innerHTML = '<div style="display:flex;align-items:center;gap:10px;padding:12px 16px 0 14px">'
      + '<div style="width:4px;min-height:20px;border-radius:2px;background:' + borderColor + ';flex-shrink:0"></div>'
      + '<div style="font-size:' + (fontSize + 2) + 'px;font-weight:600;color:var(--txt,#eaeaf2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + title + '</div>'
      + '<div style="margin-left:auto;cursor:pointer;pointer-events:auto;color:var(--txt3,#5c5c72);font-size:16px;line-height:1;padding:2px 4px" class="notify-close">&times;</div>'
      + '</div>'
      + '<div style="height:1px;background:var(--border,#2d2d44);margin:10px 16px 0 28px"></div>'
      + '<div style="font-size:' + fontSize + 'px;color:var(--txt2,#9898ac);padding:10px 16px 14px 28px;line-height:1.6">' + message + '</div>'
      + '<div style="height:3px;background:var(--bg2,#24243a);position:relative;overflow:hidden">'
      + '<div class="notify-progress" style="height:100%;background:' + borderColor + ';width:100%;transition:linear"></div>'
      + '</div>';

    container.appendChild(popup);

    var progressBar = popup.querySelector('.notify-progress');
    if (progressBar) {
      progressBar.style.transitionDuration = duration + 'ms';
      requestAnimationFrame(function() {
        requestAnimationFrame(function() {
          progressBar.style.width = '0%';
        });
      });
    }

    requestAnimationFrame(function() {
      popup.style.opacity = '1';
      popup.style.transform = 'translateY(0)';
    });

    var closeBtn = popup.querySelector('.notify-close');
    function removePopup() {
      popup.style.opacity = '0';
      popup.style.transform = 'translateY(12px)';
      setTimeout(function() { popup.remove(); }, 350);
    }
    if (closeBtn) closeBtn.addEventListener('click', removePopup);
    setTimeout(removePopup, duration);
  }
};

var nodes = {
  'plugin/notify_popup': {
    display_name: '消息弹窗',
    color: '#a855f7',
    category: 'plugin',
    icon: 'fa-solid fa-comment-dots',
    backendAction: 'notify_popup',
    inputs: [{name:'in', type:'flow'}],
    outputs: [{name:'next', type:'flow'}],
    params_schema: {
      title: {type:'string', label:'标题', default:'提示', varRef:true},
      message: {type:'string', label:'内容', default:'操作完成', varRef:true},
      sound: {type:'enum', label:'音效', default:'default', options:['default','info','success','warning','error','none']},
      custom_sound: {type:'string', label:'自定义音效文件', default:'', description:'wav/mp3文件路径，留空使用内置音效'},
      duration: {type:'number', label:'显示时长(ms)', default:3000, varRef:true},
      position: {type:'enum', label:'位置', default:'bottom-right', options:['bottom-right','bottom-left','top-right','top-left','center']},
      desktop_popup: {type:'bool', label:'桌面弹窗(不依赖App窗口)', default:false, description:'开启后使用系统级弹窗，即使App最小化也能看到'},
      font_size: {type:'number', label:'字体大小', default:12, varRef:true, description:'弹窗内容字体大小(px)'}
    },
    onExecute: function(params) {
      if (params.desktop_popup && window.pywebview && window.pywebview.api && window.pywebview.api.call_plugin) {
        window.pywebview.api.call_plugin('notify', 'notify_popup', params).then(function(res) {
          if (res && res.ok) console.log('[notify] 桌面弹窗已显示');
        }).catch(function(err) {
          _notifyHelper._showPopup(params);
        });
      } else {
        _notifyHelper._showPopup(params);
      }
    },
    onPluginEvent: function(eventName, eventData) {
      if (eventName === 'notify_popup') _notifyHelper._showPopup(eventData || {});
      if (eventName === 'notify_play_sound' && eventData) _notifyHelper._playSound(eventData.sound || 'default', eventData.custom_sound || '');
    }
  },

  'plugin/notify_sound': {
    display_name: '语音提示',
    color: '#a855f7',
    category: 'plugin',
    icon: 'fa-solid fa-volume-high',
    backendAction: 'notify_sound',
    inputs: [{name:'in', type:'flow'}],
    outputs: [{name:'next', type:'flow'}],
    params_schema: {
      text: {type:'string', label:'朗读文本', default:'操作完成', varRef:true},
      volume: {type:'number', label:'音量(0-1)', default:0.8, varRef:true},
      rate: {type:'number', label:'语速(0.5-2)', default:1.0, varRef:true},
      sound: {type:'enum', label:'提示音', default:'none', options:['default','info','success','warning','error','none']},
      custom_sound: {type:'string', label:'自定义音效文件', default:''},
      voice_name: {
        type: 'enum', label: '语音音色', default: '',
        options: ['', 'Xiaoxiao', 'Yunxi', 'Yunyang', 'Xiaoyi', 'Kangkang', 'Huihui', 'Yaoyao'],
        description: '留空为系统默认。Xiaoxiao(晓晓-女)、Yunxi(云希-男)、Yunyang(云扬-男)、Xiaoyi(晓依-女)、Kangkang(康康-男)、Huihui(慧慧-女)、Yaoyao(瑶瑶-女)'
      }
    },
    onExecute: function(params) {
      if (params.sound && params.sound !== 'none') _notifyHelper._playSound(params.sound, params.custom_sound || '');
      _notifyHelper._speak(params.text, params.volume, params.rate, params.voice_name);
    },
    onPluginEvent: function(eventName, eventData) {
      if (eventName === 'notify_sound' && eventData) {
        if (eventData.sound && eventData.sound !== 'none') _notifyHelper._playSound(eventData.sound, eventData.custom_sound || '');
        _notifyHelper._speak(eventData.text, eventData.volume, eventData.rate, eventData.voice_name);
      }
    }
  }
};

window.__plugin_nodes__ = nodes;
