/*
 * Send Webflow-designed forms to Formspree in the background.
 *
 * Forms opt in with data-formspree and an action of https://formspree.io/f/<id>.
 * Without JavaScript they still work as a normal POST to Formspree.
 *
 * With JavaScript we:
 *   - stop webflow.js from handling the submit (it would post to Webflow),
 *   - POST the fields to Formspree as JSON-accepting fetch,
 *   - show Webflow's own success (.w-form-done) or error (.w-form-fail) block,
 *     exactly as webflow.js would, so the /contact page script that watches
 *     .w-form-done (banner, "Thanks, Name!", header swap) keeps working.
 */
(function () {
  "use strict";

  function setup(form) {
    var wrapper = form.closest(".w-form") || form.parentElement;
    var done = wrapper.querySelector(".w-form-done");
    var fail = wrapper.querySelector(".w-form-fail");
    var submit = form.querySelector('[type="submit"]');

    // Capture phase on the form runs before webflow.js's delegated jQuery handler.
    form.addEventListener(
      "submit",
      function (event) {
        event.preventDefault();
        event.stopImmediatePropagation();

        if (typeof form.reportValidity === "function" && !form.reportValidity()) return;

        var original = submit ? submit.value : null;
        if (submit) {
          submit.value = submit.getAttribute("data-wait") || "Please wait...";
          submit.disabled = true;
        }
        if (fail) fail.style.display = "none";

        var data = new FormData(form);
        // Let Esther reply straight to the sender from the notification email.
        var email = form.querySelector('input[type="email"]');
        if (email && email.value) data.set("_replyto", email.value);

        fetch(form.action, {
          method: "POST",
          body: data,
          headers: { Accept: "application/json" },
        })
          .then(function (response) {
            if (!response.ok) throw new Error("Formspree responded " + response.status);
            // No form.reset(): the /contact script reads the first name when the
            // success block appears. Webflow also leaves the (hidden) form filled.
            form.style.display = "none";
            if (done) done.style.display = "block";
            // Bring the "Thank You" heading and message into view.
            var reduceMotion =
              window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
            window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" });
          })
          .catch(function (err) {
            if (window.console) console.error(err);
            if (fail) fail.style.display = "block";
          })
          .then(function () {
            if (submit) {
              submit.value = original;
              submit.disabled = false;
            }
          });
      },
      true
    );
  }

  function start() {
    document.querySelectorAll("form[data-formspree]").forEach(setup);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
