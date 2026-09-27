function adminBugReports() {
    return {
        open: false,
        reports: [],
        query: '',
        statusFilter: 'all',
        loading: true,
        error: '',
        updatingReportId: null,
        get filteredReports() {
            const query = this.query.trim().toLowerCase();
            return this.reports.filter(report => {
                const matchesStatus = this.statusFilter === 'all' || report.status === this.statusFilter;
                const searchable = [
                    report.reporter_name,
                    report.reporter_email,
                    report.reporter_role,
                    report.issue_type,
                    report.subject,
                    report.description
                ].join(' ').toLowerCase();
                return matchesStatus && (!query || searchable.includes(query));
            });
        },
        async init() {
            await this.loadReports();
        },
        async loadReports() {
            const adminUserId = localStorage.getItem('user_id');
            if (localStorage.getItem('role') !== 'admin' || !adminUserId) {
                this.loading = false;
                this.error = 'Sign in with an administrator account to review reports.';
                return;
            }

            this.loading = true;
            this.error = '';
            try {
                const response = await fetch(`/api/bug-reports/admin?admin_user_id=${encodeURIComponent(adminUserId)}`);
                const data = await response.json();
                if (!response.ok) throw new Error(data.detail || 'Unable to load bug reports.');
                this.reports = data.map(report => ({ ...report, savedStatus: report.status }));
            } catch (error) {
                this.error = error.message || 'Unable to load bug reports.';
            } finally {
                this.loading = false;
            }
        },
        async updateStatus(report) {
            if (this.updatingReportId !== null) return;
            const adminUserId = localStorage.getItem('user_id');
            const previousStatus = report.savedStatus;
            this.updatingReportId = report.report_id;
            this.error = '';
            try {
                const response = await fetch(`/api/bug-reports/admin/${encodeURIComponent(report.report_id)}/status?admin_user_id=${encodeURIComponent(adminUserId)}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: report.status })
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.detail || 'Unable to update report status.');
                report.status = data.status;
                report.savedStatus = data.status;
            } catch (error) {
                report.status = previousStatus;
                this.error = error.message || 'Unable to update report status.';
            } finally {
                this.updatingReportId = null;
            }
        },
        formatDate(value) {
            if (!value) return 'Unknown';
            return new Date(value).toLocaleString();
        }
    };
}
