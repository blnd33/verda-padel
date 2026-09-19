/* Runs before first paint (loaded synchronously in <head>) so the stored theme
   is applied without a flash, and so the preloader is skipped on pages after
   the first. Must stay tiny and dependency-free.
   No data-theme stamp means "follow the system", which the CSS handles. */
(function () {
  var root = document.documentElement;
  try {
    var t = localStorage.getItem('verda-theme');
    if (t === 'dark' || t === 'light') root.setAttribute('data-theme', t);
  } catch (e) {
    /* private mode / blocked storage: fall through to the system preference */
  }
  try {
    /* the branded intro is a first-impression, not a toll booth on every click */
    if (sessionStorage.getItem('verda-seen')) root.setAttribute('data-loader', 'skip');
  } catch (e) {
    /* no session storage: the loader simply shows again, which is harmless */
  }
})();
