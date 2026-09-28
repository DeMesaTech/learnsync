(() => {
  const segments = location.pathname.split('/').filter(Boolean);
  const role = segments[0];
  if (!['admin', 'teacher', 'student'].includes(role)) return;
  const file = segments[1] || 'dashboard.html';
  const nav = {
    admin: [
      ['Dashboard', 'dashboard.html'], ['School year & semester', 'terms.html'],
      ['Subjects', 'subjects.html'], ['Faculty & assignments', 'faculty.html'],
      ['Sections & rosters', 'sections.html'], ['Student subjects', 'student-subjects.html'],
      ['Accounts', 'accounts.html'], ['Legacy review', 'legacy-review.html'],
      ['Bug reports', 'bug-reports.html']
    ],
    teacher: [
      ['Dashboard', 'dashboard.html'], ['Assigned subjects', 'classes.html'],
      ['Activities & quizzes', 'assessments.html'],
      ['Attendance', 'attendance.html'], ['Gradebook', 'gradebook.html'],
      ['Account', 'Account.html'], ['Report a bug', 'report-bug.html']
    ],
    student: [
      ['Dashboard', 'dashboard.html'], ['Grades', 'final-grades.html'],
      ['AI assistant', 'AI.html'], ['Account', 'Account.html'],
      ['Report a bug', 'report-bug.html']
    ]
  };
  const title = {admin:'Administration', teacher:'Faculty', student:'Student'}[role];
  const header = document.createElement('header');
  header.className = 'ds-topbar';
  header.innerHTML = `<div style="display:flex;align-items:center;gap:.7rem;min-width:0">
    <button class="ds-menu-button" type="button" aria-label="Open navigation" aria-expanded="false">☰</button>
    <a class="ds-brand" href="dashboard.html"><img src="../img/gmvcc.png" alt="GMVCC"><span>LearnSync</span></a></div>
    <span class="ds-topbar-meta"></span>`;
  header.querySelector('.ds-topbar-meta').textContent = `${title} · ${localStorage.getItem('name') || 'GMVCC'}`;
  const sidebar = document.createElement('aside');
  sidebar.className = 'ds-sidebar';
  sidebar.setAttribute('aria-label', `${title} navigation`);
  const navItems = nav[role].map(([label, href]) =>
    `<a class="ds-nav-link" href="${href}" ${file === href ? 'aria-current="page"' : ''}>${label}</a>`).join('');
  sidebar.innerHTML = `<div class="ds-nav-label">${title}</div><nav>${navItems}</nav>
    <div class="ds-nav-separator"></div><a class="ds-nav-link" href="../index.html" data-ds-logout>Sign out</a>`;
  const backdrop = document.createElement('div');
  backdrop.className = 'ds-backdrop';
  const close = () => {document.body.classList.remove('ds-nav-open'); header.querySelector('button').setAttribute('aria-expanded','false');};
  header.querySelector('button').addEventListener('click', () => {
    const opened = document.body.classList.toggle('ds-nav-open');
    header.querySelector('button').setAttribute('aria-expanded', String(opened));
  });
  backdrop.addEventListener('click', close);
  sidebar.addEventListener('click', event => {if (event.target.closest('a')) close();});
  sidebar.querySelector('[data-ds-logout]').addEventListener('click', () => {
    ['user_id', 'role', 'name', 'teacher_id', 'student_id'].forEach(key => localStorage.removeItem(key));
  });
  document.body.prepend(backdrop, sidebar, header);
  document.body.classList.add('ds-enabled');

  // Shared feedback for the existing Alpine pages and the newer faculty pages.
  const toastHost = document.createElement('div');
  toastHost.className = 'ds-toast-host';
  toastHost.setAttribute('aria-live', 'polite');
  document.body.append(toastHost);
  const loadingBar = document.createElement('div');
  loadingBar.className = 'ds-loading-bar';
  loadingBar.setAttribute('role', 'progressbar');
  loadingBar.setAttribute('aria-label', 'Loading');
  document.body.append(loadingBar);
  window.LearnSyncUI = {
    toast(message, type = 'success') {
      const item = document.createElement('div');
      item.className = `ds-toast ds-toast-${type}`;
      item.setAttribute('role', type === 'error' ? 'alert' : 'status');
      const label = document.createElement('span');
      label.textContent = message;
      const closeButton = document.createElement('button');
      closeButton.type = 'button';
      closeButton.setAttribute('aria-label', 'Dismiss notification');
      closeButton.textContent = '×';
      closeButton.onclick = () => item.remove();
      item.append(label, closeButton);
      toastHost.append(item);
      if (type !== 'error') setTimeout(() => item.remove(), 5000);
    }
  };
  const originalFetch = window.fetch.bind(window);
  let activeRequests = 0;
  window.fetch = async (input, init = {}) => {
    const url = String(typeof input === 'string' ? input : input.url || '');
    if (!url.includes('/api/')) return originalFetch(input, init);
    const method = String(init.method || (input instanceof Request ? input.method : 'GET')).toUpperCase();
    const writing = !['GET', 'HEAD'].includes(method);
    const action = writing && document.activeElement?.matches('button, input[type="submit"]') ? document.activeElement : null;
    if (action) { action.disabled = true; action.classList.add('ds-busy'); }
    activeRequests++;
    loadingBar.classList.add('is-active');
    try {
      const response = await originalFetch(input, init);
      if (writing && !url.includes('/resources/import-legacy')) {
        if (response.ok) window.LearnSyncUI.toast(method === 'DELETE' ? 'Deleted successfully.' : url.includes('/generate-draft') ? 'Questions generated for review.' : 'Saved successfully.');
        else {
          const data = await response.clone().json().catch(() => ({}));
          window.LearnSyncUI.toast(typeof data.detail === 'string' ? data.detail : 'The action could not be completed.', 'error');
        }
      }
      return response;
    } catch (error) {
      window.LearnSyncUI.toast('Connection failed. Please try again.', 'error');
      throw error;
    } finally {
      activeRequests--;
      if (!activeRequests) loadingBar.classList.remove('is-active');
      if (action) { action.disabled = false; action.classList.remove('ds-busy'); }
    }
  };

  const setupTable = table => {
    if (table.dataset.dsEnhanced) return;
    const body = table.tBodies[0];
    if (!body) return;
    table.dataset.dsEnhanced = 'true';
    const wrap = table.closest('.ds-table-wrap, .lms-table-wrap') || table.parentElement;
    const controls = document.createElement('div');
    controls.className = 'ds-list-controls';
    const search = document.createElement('input');
    search.type = 'search'; search.placeholder = 'Search this list'; search.setAttribute('aria-label', 'Search table');
    const pageSize = document.createElement('select');
    pageSize.setAttribute('aria-label', 'Rows per page');
    [10,25,50].forEach(n => { const option = document.createElement('option'); option.value = n; option.textContent = `${n} rows`; pageSize.append(option); });
    const pageInfo = document.createElement('span'); pageInfo.className = 'ds-help';
    const prev = document.createElement('button'); prev.type = 'button'; prev.textContent = 'Previous';
    const next = document.createElement('button'); next.type = 'button'; next.textContent = 'Next';
    const headings = [...table.querySelectorAll('thead th')].map(th => th.textContent.trim().toLowerCase());
    const filterIndex = headings.findIndex(h => /^(status|state|role|type)$/.test(h));
    const filter = document.createElement('select'); filter.setAttribute('aria-label', 'Filter table');
    let page = 1;
    const refresh = () => {
      const rows = [...body.rows];
      const options = [...new Set(rows.map(row => row.cells[filterIndex]?.textContent.trim()).filter(Boolean))].sort();
      const selected = filter.value;
      filter.replaceChildren(new Option('All ' + (headings[filterIndex] || 'statuses'), ''));
      options.forEach(value => filter.append(new Option(value, value)));
      filter.value = options.includes(selected) ? selected : '';
      const matching = rows.filter(row => row.textContent.toLowerCase().includes(search.value.toLowerCase()) && (!filter.value || row.cells[filterIndex]?.textContent.trim() === filter.value));
      const count = Math.max(1, Math.ceil(matching.length / Number(pageSize.value)));
      page = Math.min(page, count);
      rows.forEach(row => { row.hidden = true; });
      matching.slice((page - 1) * Number(pageSize.value), page * Number(pageSize.value)).forEach(row => { row.hidden = false; });
      pageInfo.textContent = `${matching.length} results · page ${page} of ${count}`;
      prev.disabled = page <= 1; next.disabled = page >= count;
    };
    search.oninput = () => { page = 1; refresh(); };
    filter.onchange = () => { page = 1; refresh(); };
    pageSize.onchange = () => { page = 1; refresh(); };
    prev.onclick = () => { page--; refresh(); };
    next.onclick = () => { page++; refresh(); };
    controls.append(search);
    if (filterIndex >= 0) controls.append(filter);
    controls.append(pageSize, pageInfo, prev, next);
    wrap.parentNode.insertBefore(controls, wrap);
    new MutationObserver(refresh).observe(body, {childList:true, subtree:false, characterData:false});
    refresh();
  };
  const scanTables = () => document.querySelectorAll('table.ds-table, table.lms-table').forEach(setupTable);
  scanTables();
  new MutationObserver(scanTables).observe(document.body, {childList:true, subtree:true});
})();
