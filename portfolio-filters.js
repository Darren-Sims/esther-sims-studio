<script>
  document.addEventListener("DOMContentLoaded", function () {
  const filterButtons = document.querySelectorAll("[data-filter]");
  const projectItems = document.querySelectorAll("[data-category]");
  const filterToggle = document.querySelector("#filter-toggle");
  // Label element inside the accordion toggle that shows the current category
  const selectedFilter = document.querySelector(".filter-current");

  // Which filters are currently active. Starts on "all".
  let activeFilters = new Set(["all"]);

  /*
  --------------------------------
  PER-BUTTON COUNTS (static — how many pieces are in each category)
  --------------------------------
  */
  function setButtonCounts() {
    filterButtons.forEach(function (button) {
      const filter = button.getAttribute("data-filter");
      let count;
      if (filter === "all") {
        count = projectItems.length;
      } else {
        count = 0;
        projectItems.forEach(function (item) {
          if (item.getAttribute("data-category") === filter) count++;
        });
      }

      // Wrap the existing label in a span once, so we can update just the
      // count on every click without re-parsing/clobbering the label text.
      let labelSpan = button.querySelector(".filter-btn-label");
      if (!labelSpan) {
        const label = button.textContent.trim();
        button.textContent = "";
        labelSpan = document.createElement("span");
        labelSpan.className = "filter-btn-label";
        labelSpan.textContent = label;
        button.appendChild(labelSpan);
      }

      let countSpan = button.querySelector(".filter-btn-count");
      if (!countSpan) {
        countSpan = document.createElement("span");
        countSpan.className = "filter-btn-count";
        button.appendChild(countSpan);
      }
      countSpan.textContent = " (" + count + ")";
    });
  }

  /*
  --------------------------------
  FILTER FUNCTION (multi-select, OR logic)
  --------------------------------
  */
  function applyFilters() {
    projectItems.forEach(function (item) {
      const category = item.getAttribute("data-category");
      const show = activeFilters.has("all") || activeFilters.has(category);
      item.style.display = show ? "" : "none";
    });
  }

  /*
  --------------------------------
  BUTTON ACTIVE STATES
  --------------------------------
  */
  function updateActiveStates() {
    filterButtons.forEach(function (button) {
      const filter = button.getAttribute("data-filter");
      const isActive = activeFilters.has(filter);
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
  }

  /*
  --------------------------------
  ACCORDION / TOGGLE LABEL
  --------------------------------
  */
  function updateToggleLabel() {
    let label;
    if (activeFilters.has("all")) {
      label = "All";
    } else {
      // Build from the unique set of active filter values, not every button
      // instance — there are two rows of buttons sharing the same
      // data-filter values (desktop row + mobile accordion), so looping
      // buttons directly would list each selected category twice.
      const labels = [];
      activeFilters.forEach(function (filter) {
        if (filter === "all") return;
        const matchingButton = document.querySelector('[data-filter="' + filter + '"]');
        if (matchingButton) {
          const labelSpan = matchingButton.querySelector(".filter-btn-label");
          labels.push(labelSpan ? labelSpan.textContent : matchingButton.textContent.trim());
        }
      });
      label = labels.length ? labels.join(", ") : "All";
    }

    if (selectedFilter) {
      selectedFilter.textContent = label;
    } else if (filterToggle) {
      filterToggle.textContent = label;
    }
  }

  /*
  --------------------------------
  FILTER BUTTON CLICKS
  --------------------------------
  */
  filterButtons.forEach(function (button) {
    button.setAttribute("aria-pressed", "false");
    button.addEventListener("click", function (event) {
      event.preventDefault();
      const filter = button.getAttribute("data-filter");

      if (filter === "all") {
        activeFilters = new Set(["all"]);
      } else {
        activeFilters.delete("all");
        if (activeFilters.has(filter)) {
          activeFilters.delete(filter);
        } else {
          activeFilters.add(filter);
        }
        // Nothing selected? Fall back to "All" rather than showing nothing.
        if (activeFilters.size === 0) {
          activeFilters = new Set(["all"]);
        }
      }

      updateActiveStates();
      applyFilters();
      updateToggleLabel();
      updateClearButtonVisibility();

      // Auto-close on mobile only when "All" is picked — keep the panel
      // open otherwise so multiple categories can be tapped in a row.
      if (
        filter === "all" &&
        filterToggle &&
        window.matchMedia("(max-width: 767px)").matches
      ) {
        filterToggle.click();
      }
    });
  });

  /*
  --------------------------------
  CLEAR ALL FILTERS BUTTON
  --------------------------------
  */
  const clearFiltersButtons = document.querySelectorAll(".filters-clear_wrap");

  function updateClearButtonVisibility() {
    if (!clearFiltersButtons.length) return;
    // Only show once at least one category is selected — nothing to
    // clear while "All" is active.
    const hasSelection = !activeFilters.has("all");
    clearFiltersButtons.forEach(function (btn) {
      btn.style.display = hasSelection ? "" : "none";
    });
  }

  clearFiltersButtons.forEach(function (wrap) {
    wrap.addEventListener("click", function (event) {
      event.preventDefault();
      activeFilters = new Set(["all"]);
      updateActiveStates();
      applyFilters();
      updateToggleLabel();
      updateClearButtonVisibility();
    });
  });

  /*
  --------------------------------
  INITIAL STATE
  --------------------------------
  */
  setButtonCounts();
  updateActiveStates();
  applyFilters();
  updateToggleLabel();
  updateClearButtonVisibility();
});
</script>
