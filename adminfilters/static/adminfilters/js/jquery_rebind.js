(function() {
    if (!window.$) {
      window.$ = django.jQuery;
    }
    if (!window.jQuery) {
      window.jQuery = django.jQuery;
    }
})();
