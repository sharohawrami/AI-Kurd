/* Kurdistan AI Safety Hub: form behaviour for the cohort, staff and newsletter forms.
   Submissions go to the endpoint set in site.json (form_endpoint). With no endpoint
   the forms run in preview mode: they validate and confirm, but send nothing. */
(function () {
  "use strict";


  var LANG = document.documentElement.getAttribute("lang") === "ckb" ? "ckb" : "en";
  var TEXT = {
    en: {
      tick: "Tick this box to continue.",
      answer: "Answer this question to continue.",
      email: "Enter an email address like name@example.com.",
      url: "Enter a full link that starts with https://",
      tooLong: "Keep this to {max} words or fewer. You have {n}.",
      tooShort: "Write at least {min} words. You have {n}.",
      chooseMany: "Choose at least one option.",
      chooseOne: "Choose an option.",
      sumOne: "One answer needs attention",
      sumMany: "{n} answers need attention",
      word: "word", words: "words",
      range: "{min} to {max} words", upTo: "up to {max} words", atLeast: "at least {min} words",
      clearConfirm: "Click again to clear every answer",
      sending: "Sending…",
      there: "there",
      member: "a team member",
      question: "This question",
      nlPreview: "Preview: the site isn't connected to a form endpoint yet, so this address wasn't saved.",
      nlDone: "Subscribed. We'll write when there's news.",
      nlFail: "That didn't go through. Check your connection and try again.",
      language: "English"
    },
    ckb: {
      tick: "بۆ بەردەوامبوون ئەم خانەیە نیشانە بکە.",
      answer: "بۆ بەردەوامبوون وەڵامی ئەم پرسیارە بدەرەوە.",
      email: "ئیمەیڵێکی دروست بنووسە، وەک name@example.com.",
      url: "بەستەرێکی تەواو بنووسە کە بە https:// دەست پێ دەکات.",
      tooLong: "تکایە لە {max} وشە زیاتر مەنووسە. تۆ {n} وشەت نووسیوە.",
      tooShort: "لانیکەم {min} وشە بنووسە. تۆ {n} وشەت نووسیوە.",
      chooseMany: "لانیکەم یەک هەڵبژاردە دیاری بکە.",
      chooseOne: "هەڵبژاردەیەک دیاری بکە.",
      sumOne: "یەک وەڵام پێویستی بە سەرنجە",
      sumMany: "{n} وەڵام پێویستیان بە سەرنجە",
      word: "وشە", words: "وشە",
      range: "{min} بۆ {max} وشە", upTo: "هەتا {max} وشە", atLeast: "لانیکەم {min} وشە",
      clearConfirm: "دووبارە کرتە بکە بۆ سڕینەوەی هەموو وەڵامەکان",
      sending: "ناردن…",
      there: "هاوڕێ",
      member: "ئەندامی تیم",
      question: "ئەم پرسیارە",
      nlPreview: "پێشبینین: ماڵپەڕەکە هێشتا بە شوێنی وەرگرتنی فۆڕمەکان نەبەستراوەتەوە، بۆیە ئەم ناونیشانە پاشەکەوت نەکرا.",
      nlDone: "بەشداربوویت. هەر کاتێک هەواڵێکمان هەبوو، بۆت دەنووسین.",
      nlFail: "نەنێردرا. پەیوەندیی ئینتەرنێتەکەت بپشکنە و دووبارە هەوڵ بدەرەوە.",
      language: "Kurdish (Sorani)"
    }
  };
  var ROLES_KU = {
    "Course Facilitator / TA": "ڕێکخەری دانیشتن / یاریدەدەری وانە",
    "Research and Reading Group Lead": "سەرپەرشتیاری گروپی خوێندنەوە",
    "Operations and Community Manager": "بەڕێوەبەری کارگێڕی و کۆمەڵگە",
    "Other contribution": "بەشداریی تر"
  };
  function digits(s) {
    s = String(s);
    return LANG === "ckb" ? s.replace(/[0-9]/g, function (d) { return "٠١٢٣٤٥٦٧٨٩".charAt(+d); }) : s;
  }
  function T(key, vars) {
    var s = TEXT[LANG][key];
    Object.keys(vars || {}).forEach(function (k) { s = s.split("{" + k + "}").join(digits(vars[k])); });
    return s;
  }

  var meta = document.querySelector('meta[name="kaish-endpoint"]');
  var ENDPOINT = meta ? (meta.getAttribute("content") || "").trim() : "";

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function countWords(t) { t = (t || "").trim(); return t ? t.split(/\s+/).length : 0; }
  function cssEscape(s) { return window.CSS && CSS.escape ? CSS.escape(s) : s.replace(/"/g, '\\"'); }

  var store = {
    get: function (k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { window.localStorage.setItem(k, v); } catch (e) { /* storage unavailable */ } },
    del: function (k) { try { window.localStorage.removeItem(k); } catch (e) { /* storage unavailable */ } }
  };

  function controlsNamed(form, name) {
    return $$('[name="' + cssEscape(name) + '"]', form);
  }

  function selectedValues(form, name) {
    return controlsNamed(form, name).filter(function (el) {
      if (el.type === "checkbox" || el.type === "radio") return el.checked;
      return true;
    }).map(function (el) { return el.value; });
  }

  /* ---------- conditional questions: data-show-if="name=Value|Other" ---------- */
  function applyConditions(form) {
    $$("[data-show-if]", form).forEach(function (el) {
      var spec = el.getAttribute("data-show-if");
      var i = spec.indexOf("=");
      var name = spec.slice(0, i);
      var wanted = spec.slice(i + 1).split("|");
      var show = selectedValues(form, name).some(function (v) { return wanted.indexOf(v) !== -1; });
      el.hidden = !show;
      $$("input, select, textarea", el).forEach(function (c) { c.disabled = !show; });
    });
    // A question nested inside a hidden block stays disabled.
    $$("[data-show-if][hidden] input, [data-show-if][hidden] select, [data-show-if][hidden] textarea", form)
      .forEach(function (c) { c.disabled = true; });
  }

  /* ---------- word counters ---------- */
  function wordRange(min, max) {
    if (min && max) return T("range", { min: min, max: max });
    if (max) return T("upTo", { max: max });
    return T("atLeast", { min: min });
  }
  function setupCounters(form) {
    $$("textarea[data-min-words], textarea[data-max-words]", form).forEach(function (ta) {
      var min = parseInt(ta.getAttribute("data-min-words"), 10) || 0;
      var max = parseInt(ta.getAttribute("data-max-words"), 10) || 0;
      var out = document.createElement("p");
      out.className = "wc";
      out.id = ta.id + "-wc";
      ta.insertAdjacentElement("afterend", out);
      var described = (ta.getAttribute("aria-describedby") || "").trim();
      ta.setAttribute("aria-describedby", (described + " " + out.id).trim());
      function update() {
        var n = countWords(ta.value);
        out.textContent = digits(n) + " " + (n === 1 ? T("word") : T("words")) + " · " + wordRange(min, max);
        out.classList.toggle("bad", (max && n > max) || (min && n > 0 && n < min));
      }
      ta.addEventListener("input", update);
      ta._updateCount = update;
      update();
    });
  }

  /* ---------- validation ---------- */
  function labelFor(container) {
    var l = $(":scope > label, :scope > legend, :scope > .q", container);
    var text = l ? l.textContent : T("question");
    return text.replace(/\*/g, "").replace(/\s+/g, " ").replace(/(optional|ئارەزوومەندانە)$/i, "").trim();
  }

  function clearErrors(form) {
    $$(".invalid", form).forEach(function (f) { f.classList.remove("invalid"); });
    $$(".err", form).forEach(function (e) { e.remove(); });
    $$("[aria-invalid]", form).forEach(function (e) { e.removeAttribute("aria-invalid"); });
  }

  function flag(container, message, focusEl, list) {
    if (container.classList.contains("invalid")) return;
    container.classList.add("invalid");
    var p = document.createElement("p");
    p.className = "err";
    p.id = (focusEl.id || focusEl.name) + "-err";
    p.textContent = message;
    container.appendChild(p);
    focusEl.setAttribute("aria-invalid", "true");
    var described = (focusEl.getAttribute("aria-describedby") || "").trim();
    if (described.indexOf(p.id) === -1) focusEl.setAttribute("aria-describedby", (described + " " + p.id).trim());
    list.push({ el: focusEl, text: labelFor(container) + ": " + message });
  }

  function validate(form) {
    clearErrors(form);
    var errs = [];
    $$("input, select, textarea", form).forEach(function (el) {
      if (el.disabled || !el.name || el.name === "website") return;
      if (el.type === "radio" || (el.type === "checkbox" && el.closest("[data-required-group]"))) return;
      var box = el.closest(".field") || el.parentElement;
      var v = (el.value || "").trim();
      if (el.type === "checkbox") {
        if (el.required && !el.checked) flag(box, T("tick"), el, errs);
        return;
      }
      if (el.required && !v) { flag(box, T("answer"), el, errs); return; }
      if (v && el.type === "email" && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)) {
        flag(box, T("email"), el, errs); return;
      }
      if (v && el.type === "url" && !/^https?:\/\/\S+\.\S+/.test(v)) {
        flag(box, T("url"), el, errs); return;
      }
      if (el.tagName === "TEXTAREA") {
        var n = countWords(v);
        var min = parseInt(el.getAttribute("data-min-words"), 10) || 0;
        var max = parseInt(el.getAttribute("data-max-words"), 10) || 0;
        if (max && n > max) flag(box, T("tooLong", { max: max, n: n }), el, errs);
        else if (min && v && n < min) flag(box, T("tooShort", { min: min, n: n }), el, errs);
      }
    });
    $$("[data-required-group]", form).forEach(function (group) {
      if (group.closest("[hidden]")) return;
      var name = group.getAttribute("data-required-group");
      var inputs = controlsNamed(form, name).filter(function (i) { return !i.disabled; });
      if (!inputs.length) return;
      if (!inputs.some(function (i) { return i.checked; })) {
        var msg = inputs[0].type === "checkbox" ? T("chooseMany") : T("chooseOne");
        flag(group, msg, inputs[0], errs);
      }
    });
    $$("[data-ineligible]", form).forEach(function (el) {
      if (el.checked && !el.disabled) flag(el.closest(".field"), el.getAttribute("data-ineligible"), el, errs);
    });
    // Report in the order the questions appear.
    errs.sort(function (a, b) {
      return a.el.compareDocumentPosition(b.el) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
    });
    return errs;
  }

  function showSummary(form, errs) {
    var box = $(".errsum", form.parentElement);
    if (!box) return;
    box.innerHTML = "";
    var h = document.createElement("h2");
    h.textContent = errs.length === 1 ? T("sumOne") : T("sumMany", { n: errs.length });
    var ul = document.createElement("ul");
    errs.forEach(function (e) {
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = "#" + e.el.id;
      a.textContent = e.text;
      a.addEventListener("click", function (ev) {
        ev.preventDefault();
        e.el.focus();
        e.el.scrollIntoView({ block: "center" });
      });
      li.appendChild(a);
      ul.appendChild(li);
    });
    box.appendChild(h);
    box.appendChild(ul);
    box.hidden = false;
    box.focus();
    box.scrollIntoView({ block: "start" });
  }

  /* ---------- drafts (this browser only) ---------- */
  function draftKey(form) {
    var f = form.getAttribute("data-form") || "";
    return "kaish-draft-" + form.id + (f.indexOf("course:") === 0 ? "-" + f.slice(7) : "");
  }

  function snapshot(form) {
    var data = {};
    $$("input, select, textarea", form).forEach(function (el) {
      if (!el.name || el.name === "website" || el.type === "file") return;
      if (el.type === "checkbox" || el.type === "radio") {
        if (el.checked) (data[el.name] = data[el.name] || []).push(el.value);
      } else if (el.value) {
        data[el.name] = el.value;
      }
    });
    return data;
  }

  function restore(form, data) {
    $$("input, select, textarea", form).forEach(function (el) {
      if (!el.name || !(el.name in data)) return;
      if (el.type === "checkbox" || el.type === "radio") el.checked = data[el.name].indexOf(el.value) !== -1;
      else el.value = data[el.name];
    });
  }

  function setupDraft(form) {
    var note = $(".draft", form.parentElement);
    var raw = store.get(draftKey(form));
    if (raw) {
      try {
        var data = JSON.parse(raw);
        if (Object.keys(data).length) {
          restore(form, data);
          if (note) note.hidden = false;
        }
      } catch (e) { store.del(draftKey(form)); }
    }
    var timer = null;
    form.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () { store.set(draftKey(form), JSON.stringify(snapshot(form))); }, 500);
    });
    var clear = note && $(".linkbtn", note);
    if (clear) {
      clear.addEventListener("click", function () {
        if (clear.getAttribute("data-armed") !== "1") {
          clear.setAttribute("data-armed", "1");
          clear.textContent = T("clearConfirm");
          return;
        }
        store.del(draftKey(form));
        form.reset();
        applyConditions(form);
        $$("textarea", form).forEach(function (t) { if (t._updateCount) t._updateCount(); });
        clearErrors(form);
        note.hidden = true;
      });
    }
  }

  /* ---------- sending ---------- */
  function collect(form) {
    var fields = {};
    $$("input, select, textarea", form).forEach(function (el) {
      if (!el.name || el.disabled || el.name === "website" || el.type === "file") return;
      if (el.type === "checkbox" || el.type === "radio") {
        if (!el.checked) return;
        fields[el.name] = fields[el.name] ? fields[el.name] + "; " + el.value : el.value;
      } else {
        fields[el.name] = (el.value || "").trim();
      }
    });
    return fields;
  }

  function send(form) {
    var payload = {
      form: form.getAttribute("data-form"),
      page: location.pathname,
      website: form.elements.website ? form.elements.website.value : "",
      fields: collect(form)
    };
    if (!payload.fields.language) payload.fields.language = T("language");
    if (!ENDPOINT) return Promise.resolve({ ok: true, preview: true, payload: payload });
    return fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "text/plain;charset=utf-8" },
      body: JSON.stringify(payload)
    }).then(function (r) {
      return r.json().catch(function () { return { ok: r.ok }; });
    }).then(function (res) {
      if (!res || !res.ok) throw new Error((res && res.error) || "not accepted");
      return { ok: true, payload: payload };
    });
  }

  function setupApplication(form) {
    setupCounters(form);
    setupDraft(form);
    applyConditions(form);
    form.addEventListener("change", function () { applyConditions(form); });
    var summary = $(".errsum", form.parentElement);
    var sendErr = $(".send-error", form.parentElement);
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      applyConditions(form);
      var errs = validate(form);
      if (errs.length) { showSummary(form, errs); return; }
      if (summary) summary.hidden = true;
      if (sendErr) sendErr.hidden = true;
      var btn = $('[type="submit"]', form);
      var label = btn.textContent;
      btn.disabled = true;
      btn.textContent = T("sending");
      send(form).then(function (res) {
        store.del(draftKey(form));
        var done = document.getElementById(form.getAttribute("data-confirm"));
        var first = (res.payload.fields.full_name || "").split(/\s+/)[0];
        $$("[data-first-name]", done).forEach(function (s) { s.textContent = first || T("there"); });
        var roles = res.payload.fields.roles;
        if (roles && LANG === "ckb") roles = roles.split("; ").map(function (r) { return ROLES_KU[r] || r; }).join("، ");
        $$("[data-roles]", done).forEach(function (s) { s.textContent = roles || T("member"); });
        $$(".preview-note", done).forEach(function (n) { n.hidden = !res.preview; });
        var note = $(".draft", form.parentElement);
        if (note) note.hidden = true;
        form.hidden = true;
        done.hidden = false;
        done.focus();
        done.scrollIntoView({ block: "start" });
      }).catch(function () {
        btn.disabled = false;
        btn.textContent = label;
        if (sendErr) { sendErr.hidden = false; sendErr.focus(); }
      });
    });
  }

  function setupNewsletter(form) {
    var msg = $(".nl-msg", form);
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var email = form.elements.email;
      var v = (email.value || "").trim();
      msg.classList.remove("err-text");
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)) {
        msg.textContent = T("email");
        msg.classList.add("err-text");
        email.setAttribute("aria-invalid", "true");
        email.focus();
        return;
      }
      email.removeAttribute("aria-invalid");
      var btn = $('[type="submit"]', form);
      btn.disabled = true;
      send(form).then(function (res) {
        msg.textContent = res.preview ? T("nlPreview") : T("nlDone");
        form.reset();
      }).catch(function () {
        msg.textContent = T("nlFail");
        msg.classList.add("err-text");
      }).then(function () { btn.disabled = false; });
    });
  }

  $$("form[data-form]").forEach(function (form) {
    if (form.getAttribute("data-form") === "newsletter") setupNewsletter(form);
    else setupApplication(form);
  });
})();

/* Glass bar: slides in once the masthead has scrolled out of view. */
(function () {
  "use strict";
  var bar = document.getElementById("glassbar");
  var head = document.querySelector(".site-header");
  if (!bar || !head || !("IntersectionObserver" in window)) return;
  new IntersectionObserver(function (entries) {
    var show = !entries[0].isIntersecting && entries[0].boundingClientRect.top < 0;
    bar.classList.toggle("on", show);
    if (show) bar.removeAttribute("inert"); else bar.setAttribute("inert", "");
  }).observe(head);
})();

/* Profile: show a newly chosen picture inside the woven frame before saving. */
(function () {
  "use strict";
  var input = document.getElementById("p-picture");
  var frame = document.querySelector("#pe-portrait .pf-photo");
  if (!input || !frame || !window.URL) return;
  var remove = document.getElementById("p-remove");
  input.addEventListener("change", function () {
    var file = input.files && input.files[0];
    if (!file || !/^image\/(jpeg|png|webp)$/.test(file.type)) return;
    var img = new Image();
    img.alt = "";
    img.src = URL.createObjectURL(file);
    frame.textContent = "";
    frame.appendChild(img);
    if (remove) remove.checked = false;
  });
})();

/* Light / dark switch. Follows the device until the visitor chooses; the choice is remembered. */
(function () {
  "use strict";
  var KEY = "kaish-theme", root = document.documentElement;
  var buttons = Array.prototype.slice.call(document.querySelectorAll("[data-theme-toggle]"));
  if (!buttons.length) return;
  var mq = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  function current() {
    var t = root.getAttribute("data-theme");
    if (t === "dark" || t === "light") return t;
    return mq && mq.matches ? "dark" : "light";
  }
  function sync() {
    var dark = current() === "dark";
    buttons.forEach(function (b) { b.setAttribute("aria-pressed", dark ? "true" : "false"); });
  }
  buttons.forEach(function (b) {
    b.hidden = false;
    b.addEventListener("click", function () {
      var next = current() === "dark" ? "light" : "dark";
      root.classList.add("theme-fade");
      root.setAttribute("data-theme", next);
      try { localStorage.setItem(KEY, next); } catch (e) {}
      sync();
      setTimeout(function () { root.classList.remove("theme-fade"); }, 450);
    });
  });
  if (mq) {
    if (mq.addEventListener) mq.addEventListener("change", sync);
    else if (mq.addListener) mq.addListener(sync);
  }
  sync();
})();

/* Weekly availability table: click a square, drag a rectangle across several with a mouse,
   or click a day or hour to fill a whole column or row. Squares are real checkboxes. */
(function () {
  "use strict";
  var KU = document.documentElement.lang === "ckb";
  var KU_DIGITS = "٠١٢٣٤٥٦٧٨٩";
  function num(n) { return KU ? String(n).replace(/[0-9]/g, function (d) { return KU_DIGITS[d]; }) : String(n); }
  Array.prototype.slice.call(document.querySelectorAll("[data-avail]")).forEach(function (wrap) {
    var boxes = Array.prototype.slice.call(wrap.querySelectorAll('input[type="checkbox"]'));
    var count = wrap.querySelector(".avail-count");
    var form = wrap.closest("form");
    function update() {
      var n = boxes.filter(function (b) { return b.checked; }).length;
      if (!count) return;
      if (!n) { count.textContent = ""; return; }
      count.textContent = KU ? num(n) + " کاتژمێر لە هەفتەیەکدا هەڵبژێردراوە" : n + (n === 1 ? " hour" : " hours") + " a week selected";
    }
    function changed() {
      update();
      if (form) {
        form.dispatchEvent(new Event("input", { bubbles: true }));
        form.dispatchEvent(new Event("change", { bubbles: true }));
      }
    }
    // Dragging ticks (or clears) the whole rectangle between the first square and the current one.
    var dragTo = null, start = null, before = null, swallowClick = false;
    function pos(input) { return [+input.getAttribute("data-col"), +input.getAttribute("data-row")]; }
    wrap.addEventListener("pointerdown", function (e) {
      if (e.pointerType !== "mouse" || e.button !== 0) return;
      var cell = e.target.closest(".avail-cell");
      if (!cell) return;
      e.preventDefault();
      var box = cell.querySelector("input");
      before = boxes.map(function (b) { return b.checked; });
      start = pos(box);
      dragTo = !box.checked;
      box.checked = dragTo;
      box.focus({ preventScroll: true });
      swallowClick = true;
      update();
    });
    wrap.addEventListener("pointerover", function (e) {
      if (dragTo === null) return;
      var cell = e.target.closest(".avail-cell");
      if (!cell) return;
      var end = pos(cell.querySelector("input"));
      var c0 = Math.min(start[0], end[0]), c1 = Math.max(start[0], end[0]);
      var r0 = Math.min(start[1], end[1]), r1 = Math.max(start[1], end[1]);
      boxes.forEach(function (b, i) {
        var p = pos(b);
        b.checked = (p[0] >= c0 && p[0] <= c1 && p[1] >= r0 && p[1] <= r1) ? dragTo : before[i];
      });
      update();
    });
    document.addEventListener("pointerup", function () {
      if (dragTo === null) return;
      dragTo = null;
      changed();
      setTimeout(function () { swallowClick = false; }, 0);
    });
    wrap.addEventListener("click", function (e) {
      var head = e.target.closest(".avail-day, .avail-hour");
      if (head) {
        var key = head.classList.contains("avail-day") ? "col" : "row";
        var group = boxes.filter(function (b) { return b.getAttribute("data-" + key) === head.getAttribute("data-" + key); });
        var all = group.every(function (b) { return b.checked; });
        group.forEach(function (b) { b.checked = !all; });
        changed();
        return;
      }
      if (swallowClick && e.target.closest(".avail-cell")) e.preventDefault();
    }, true);
    wrap.addEventListener("change", update);
    if (form) form.addEventListener("reset", function () { setTimeout(update, 0); });
    update();
  });
})();
