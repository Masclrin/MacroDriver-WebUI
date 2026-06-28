import { showToast } from '../app/toast.js';

var _searchResults = [];
var _searchIndex = -1;
var _searchVisible = false;

export function initNodeSearch() {
  var searchFloat = document.getElementById('search-float');
  var searchInp = document.getElementById('nd-search-in');
  var searchClear = document.getElementById('nd-search-clear');
  var searchPrev = document.getElementById('nd-search-prev');
  var searchNext = document.getElementById('nd-search-next');
  var searchCount = document.getElementById('nd-search-count');
  var searchDropdown = document.getElementById('nd-search-dropdown');
  var searchHeader = document.getElementById('sf-header');
  var searchClose = document.getElementById('sf-close');

  if (!searchFloat || !searchInp) return;

  function performSearch(query) {
    var nodes = window.AutomationCore.getNodes();
    _searchResults = [];
    _searchIndex = -1;
    if (!query) {
      window.AutomationCore.clearAllHighlights();
      if (searchCount) searchCount.textContent = '';
      if (searchDropdown) searchDropdown.style.display = 'none';
      return;
    }
    var qLower = query.toLowerCase();
    for (var i = 0; i < nodes.length; i++) {
      var n = nodes[i];
      var defKey = n._defKey || n.type || '';
      var name = n._customName || '';
      var def = window.AutomationNodes ? window.AutomationNodes.getNodeDef(defKey) : null;
      var defName = def ? def.display_name || '' : defKey;
      if (
        name.toLowerCase().indexOf(qLower) >= 0 ||
        defName.toLowerCase().indexOf(qLower) >= 0 ||
        defKey.toLowerCase().indexOf(qLower) >= 0 ||
        String(n.id).indexOf(qLower) >= 0
      ) {
        _searchResults.push(n);
      }
    }
    window.AutomationCore.clearAllHighlights();
    for (var j = 0; j < _searchResults.length; j++) {
      window.AutomationCore.setNodeHighlight(_searchResults[j].id, 'search-match');
    }
    if (searchCount) searchCount.textContent = _searchResults.length ? _searchResults.length + ' 个匹配' : '无匹配';
    if (_searchResults.length > 0) {
      navigateToResult(0);
    }
    renderDropdown();
  }

  function renderDropdown() {
    if (!searchDropdown) return;
    if (_searchResults.length === 0) {
      searchDropdown.style.display = 'none';
      return;
    }
    searchDropdown.style.display = 'block';
    var maxShow = Math.min(_searchResults.length, 12);
    var html = '';
    for (var i = 0; i < maxShow; i++) {
      var n = _searchResults[i];
      var defKey = n._defKey || n.type || '';
      var def = window.AutomationNodes ? window.AutomationNodes.getNodeDef(defKey) : null;
      var defName = def ? def.display_name || '' : defKey;
      var label = n._customName || defName || defKey;
      var isActive = i === _searchIndex ? ' ns-dr-active' : '';
      html += '<div class="ns-dr-item' + isActive + '" data-idx="' + i + '" data-nid="' + n.id + '">';
      html += '<span class="ns-dr-name">' + label.replace(/</g, '&lt;') + '</span>';
      html += '<span class="ns-dr-id">#' + n.id + '</span>';
      html += '</div>';
    }
    if (_searchResults.length > maxShow) {
      html += '<div class="ns-dr-more">还有 ' + (_searchResults.length - maxShow) + ' 个结果...</div>';
    }
    searchDropdown.innerHTML = html;

    searchDropdown.querySelectorAll('.ns-dr-item').forEach(function(item) {
      item.addEventListener('mousedown', function(e) {
        e.preventDefault();
        var idx = parseInt(this.dataset.idx);
        navigateToResult(idx);
        searchInp.focus();
      });
    });
  }

  function navigateToResult(idx) {
    if (_searchResults.length === 0) return;
    _searchIndex = ((idx % _searchResults.length) + _searchResults.length) % _searchResults.length;
    var target = _searchResults[_searchIndex];
    window.AutomationCore.selectNode(target);
    if (window.AutomationProperty) window.AutomationProperty.render(target);

    var el = document.getElementById('nd-' + target.id);
    if (el) {
      var prevActive = document.querySelector('.nd.search-active');
      if (prevActive) prevActive.classList.remove('search-active');
      el.classList.add('search-active');
    }

    var areaR = _getCanvasAreaRect();
    if (areaR) {
      var nodeCX = target.pos[0] + (target.size ? target.size[0] / 2 : 100);
      var nodeCY = target.pos[1] + (target.size ? target.size[1] / 2 : 40);
      var scale = window.AutomationCore.getViewportScale();
      var newOffX = areaR.width / 2 - nodeCX * scale;
      var newOffY = areaR.height / 2 - nodeCY * scale;
      window.AutomationCore.setViewport(newOffX, newOffY, scale);
    }

    if (searchCount) searchCount.textContent = (_searchIndex + 1) + '/' + _searchResults.length;
    renderDropdown();
  }

  function _getCanvasAreaRect() {
    var cvArea = document.getElementById('cv-area');
    return cvArea ? cvArea.getBoundingClientRect() : null;
  }

  function showSearchFloat() {
    searchFloat.classList.add('visible');
    _searchVisible = true;
    if (!searchFloat.style.left) {
      var areaR = _getCanvasAreaRect();
      if (areaR) {
        searchFloat.style.left = (areaR.left + areaR.width - 340) + 'px';
        searchFloat.style.top = (areaR.top + 10) + 'px';
        searchFloat.style.right = '';
      }
    }
    setTimeout(function() { searchInp.focus(); }, 50);
  }

  function hideSearchFloat() {
    searchFloat.classList.remove('visible');
    _searchVisible = false;
    performSearch('');
  }

  if (searchClose) {
    searchClose.addEventListener('click', function() { hideSearchFloat(); });
  }

  searchInp.addEventListener('input', function() {
    var val = this.value.trim();
    searchClear.style.display = val ? 'flex' : 'none';
    if (searchPrev) searchPrev.style.display = val ? 'flex' : 'none';
    if (searchNext) searchNext.style.display = val ? 'flex' : 'none';
    performSearch(val);
  });

  searchInp.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (_searchResults.length > 0) {
        navigateToResult(e.shiftKey ? _searchIndex - 1 : _searchIndex + 1);
      }
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (_searchResults.length > 0) {
        navigateToResult(_searchIndex + 1);
      }
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (_searchResults.length > 0) {
        navigateToResult(_searchIndex - 1);
      }
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      this.value = '';
      searchClear.style.display = 'none';
      if (searchPrev) searchPrev.style.display = 'none';
      if (searchNext) searchNext.style.display = 'none';
      performSearch('');
      this.blur();
    }
  });

  searchInp.addEventListener('focus', function() {
    if (this.value.trim()) {
      performSearch(this.value.trim());
    }
  });

  if (searchClear) {
    searchClear.addEventListener('click', function() {
      searchInp.value = '';
      searchClear.style.display = 'none';
      if (searchPrev) searchPrev.style.display = 'none';
      if (searchNext) searchNext.style.display = 'none';
      if (searchCount) searchCount.textContent = '';
      if (searchDropdown) searchDropdown.style.display = 'none';
      performSearch('');
      searchInp.focus();
    });
  }

  if (searchPrev) {
    searchPrev.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      navigateToResult(_searchIndex - 1);
      searchInp.focus();
    });
  }

  if (searchNext) {
    searchNext.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      navigateToResult(_searchIndex + 1);
      searchInp.focus();
    });
  }

  document.addEventListener('click', function(e) {
    if (searchDropdown && !searchDropdown.contains(e.target) && e.target !== searchInp) {
      searchDropdown.style.display = 'none';
    }
  });

  if (searchHeader) {
    var dragging = false, startX, startY, startLeft, startTop;
    searchHeader.addEventListener('mousedown', function(e) {
      if (e.target.closest('button') || e.target.closest('input')) return;
      dragging = true;
      startX = e.clientX;
      startY = e.clientY;
      var rect = searchFloat.getBoundingClientRect();
      startLeft = rect.left;
      startTop = rect.top;
      e.preventDefault();
    });
    document.addEventListener('mousemove', function(e) {
      if (!dragging) return;
      var dx = e.clientX - startX;
      var dy = e.clientY - startY;
      searchFloat.style.left = (startLeft + dx) + 'px';
      searchFloat.style.top = (startTop + dy) + 'px';
      searchFloat.style.right = '';
    });
    document.addEventListener('mouseup', function() { dragging = false; });
  }

  document.addEventListener('keydown', function(e) {
    if (e.ctrlKey && e.key === 'f') {
      var tag = (e.target || e.srcElement).tagName.toLowerCase();
      if (tag !== 'input' && tag !== 'textarea' && tag !== 'select') {
        e.preventDefault();
        if (!_searchVisible) {
          showSearchFloat();
        } else {
          searchInp.focus();
          searchInp.select();
        }
      }
    }
  });

  window._showSearchFloat = showSearchFloat;
  window._hideSearchFloat = hideSearchFloat;
}
