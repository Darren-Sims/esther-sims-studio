/*
 * Portfolio page: category filters + "Load more" pagination + back-to-top.
 *
 * Replaces the old pair of scripts (portfolio-filters.js from jsDelivr and the
 * inline Load More script). Both used to set item.style.display directly, so
 * whichever ran last won. Here a single render() decides visibility:
 *   1. filter the cards by the active categories, then
 *   2. show the first `shown` of the filtered cards.
 *
 * Markup it relies on (unchanged from the Webflow build):
 *   [data-gallery="portfolio-gallery"]  gallery; its children are the cards
 *   [data-category]                     each card's category
 *   [data-filter]                       filter buttons ("all" or a category);
 *                                       two rows share values (desktop + mobile)
 *   #filter-toggle, .filter-current     mobile accordion header + label
 *   .filters-clear_wrap                 "Clear all" buttons
 *   [data-load-more="true"]             Load more button
 *   [data-back-to-top="true"]           back-to-top button; .is-visible shows it
 */
(function () {
  "use strict";

  var PAGE_SIZE = 9;

  function init() {
    var gallery = document.querySelector('[data-gallery="portfolio-gallery"]');
    if (!gallery) return;

    var items = Array.prototype.filter.call(gallery.children, function (el) {
      return el.hasAttribute("data-category");
    });
    var filterButtons = document.querySelectorAll("[data-filter]");
    var filterToggle = document.querySelector("#filter-toggle");
    var selectedFilter = document.querySelector(".filter-current");
    var clearButtons = document.querySelectorAll(".filters-clear_wrap");
    var loadMoreBtn = document.querySelector('[data-load-more="true"]');

    var activeFilters = new Set(["all"]);
    var shown = PAGE_SIZE;

    function matches(item) {
      return activeFilters.has("all") || activeFilters.has(item.getAttribute("data-category"));
    }

    function filteredItems() {
      return items.filter(matches);
    }

    // ---------------------------------------------------------------- render
    function render(newlyRevealed) {
      var visible = filteredItems();
      items.forEach(function (item) {
        var idx = visible.indexOf(item);
        var show = idx !== -1 && idx < shown;
        item.style.display = show ? "" : "none";
        if (!newlyRevealed || newlyRevealed.indexOf(item) === -1) {
          item.classList.remove("fade-in-item", "is-shown");
        }
      });
      updateLoadMore(visible.length);
    }

    function updateLoadMore(total) {
      if (!loadMoreBtn) return;
      var remaining = total - shown;
      if (remaining <= 0) {
        loadMoreBtn.style.display = "none";
        return;
      }
      loadMoreBtn.style.display = "";
      loadMoreBtn.textContent =
        "Show " + Math.min(PAGE_SIZE, remaining) + " more (" + remaining + " remaining)";
    }

    function loadMore() {
      var visible = filteredItems();
      var previous = shown;
      shown = Math.min(shown + PAGE_SIZE, visible.length);
      var revealed = visible.slice(previous, shown);
      revealed.forEach(function (item) {
        item.classList.add("fade-in-item");
      });
      render(revealed);
      // Two frames so the browser applies the start state before the transition.
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          revealed.forEach(function (item) {
            item.classList.add("is-shown");
          });
        });
      });
    }

    // ---------------------------------------------------------------- filters
    function setButtonCounts() {
      filterButtons.forEach(function (button) {
        var filter = button.getAttribute("data-filter");
        var count =
          filter === "all"
            ? items.length
            : items.filter(function (i) {
                return i.getAttribute("data-category") === filter;
              }).length;

        var labelSpan = button.querySelector(".filter-btn-label");
        if (!labelSpan) {
          var label = button.textContent.trim();
          button.textContent = "";
          labelSpan = document.createElement("span");
          labelSpan.className = "filter-btn-label";
          labelSpan.textContent = label;
          button.appendChild(labelSpan);
        }
        var countSpan = button.querySelector(".filter-btn-count");
        if (!countSpan) {
          countSpan = document.createElement("span");
          countSpan.className = "filter-btn-count";
          button.appendChild(countSpan);
        }
        countSpan.textContent = " (" + count + ")";
      });
    }

    function updateFilterUI() {
      filterButtons.forEach(function (button) {
        var active = activeFilters.has(button.getAttribute("data-filter"));
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", active ? "true" : "false");
      });

      // Label from the unique active values, not every button (two rows share values).
      var label = "All";
      if (!activeFilters.has("all")) {
        var labels = [];
        activeFilters.forEach(function (filter) {
          var btn = document.querySelector('[data-filter="' + filter + '"]');
          if (!btn) return;
          var span = btn.querySelector(".filter-btn-label");
          labels.push(span ? span.textContent : btn.textContent.trim());
        });
        if (labels.length) label = labels.join(", ");
      }
      if (selectedFilter) selectedFilter.textContent = label;
      else if (filterToggle) filterToggle.textContent = label;

      var hasSelection = !activeFilters.has("all");
      clearButtons.forEach(function (btn) {
        btn.style.display = hasSelection ? "" : "none";
      });
    }

    function applyFilterChange() {
      shown = PAGE_SIZE; // start pagination again for the new selection
      updateFilterUI();
      render();
    }

    filterButtons.forEach(function (button) {
      button.setAttribute("aria-pressed", "false");
      button.addEventListener("click", function (event) {
        event.preventDefault();
        var filter = button.getAttribute("data-filter");
        if (filter === "all") {
          activeFilters = new Set(["all"]);
        } else {
          activeFilters.delete("all");
          if (activeFilters.has(filter)) activeFilters.delete(filter);
          else activeFilters.add(filter);
          if (activeFilters.size === 0) activeFilters = new Set(["all"]);
        }
        applyFilterChange();

        // On mobile, close the accordion only when "All" is picked, so several
        // categories can be tapped in a row.
        if (filter === "all" && filterToggle && window.matchMedia("(max-width: 767px)").matches) {
          filterToggle.click();
        }
      });
    });

    clearButtons.forEach(function (wrap) {
      wrap.addEventListener("click", function (event) {
        event.preventDefault();
        activeFilters = new Set(["all"]);
        applyFilterChange();
      });
    });

    if (loadMoreBtn) {
      loadMoreBtn.addEventListener("click", function (event) {
        event.preventDefault();
        loadMore();
      });
    }

    setButtonCounts();
    updateFilterUI();
    render();
  }

  // ---------------------------------------------------------------- back to top
  function initBackToTop() {
    var topBtn = document.querySelector('[data-scroll-top="true"]');
    if (!topBtn) return;

    topBtn.addEventListener("click", function (event) {
      event.preventDefault();
      window.scrollTo({ top: 0, behavior: "smooth" });
    });

    // Show once the hero has scrolled out of view. On short pages (e.g. a wide
    // desktop showing only 9 cards) the hero may never fully leave, so fall back
    // to "scrolled more than 60% of the viewport height". Checked on scroll and
    // resize rather than with IntersectionObserver so it behaves the same with
    // any scroll setup.
    var hero = document.querySelector(".is-hero");
    var ticking = false;

    function update() {
      ticking = false;
      var pastHero = hero ? hero.getBoundingClientRect().bottom <= 0 : false;
      var scrolledFar = window.scrollY > window.innerHeight * 0.6;
      topBtn.classList.toggle("is-visible", pastHero || scrolledFar);
    }

    function schedule() {
      if (!ticking) {
        ticking = true;
        window.requestAnimationFrame(update);
      }
    }

    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    update();
  }

  function start() {
    init();
    initBackToTop();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
