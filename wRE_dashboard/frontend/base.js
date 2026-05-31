(function () {
  var path = window.location.pathname;
  if (!path.endsWith('/')) {
    path = path.substring(0, path.lastIndexOf('/') + 1);
  }
  window.__BASE_PATH__ = path;
  var base = document.createElement('base');
  base.href = path || '/';
  document.head.appendChild(base);
})();
