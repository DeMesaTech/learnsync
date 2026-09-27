function bugReportApp(reporterRole) {
    return {
        open: false,
        reporterRole,
        form: { issue_type: '', subject: '', description: '' },
        submitting: false,
        successMessage: '',
        errorMessage: '',
        async submitReport() {
            this.successMessage = '';
            this.errorMessage = '';
            const userId = localStorage.getItem('user_id');
            if (!userId || localStorage.getItem('role') !== this.reporterRole) {
                this.errorMessage = 'Sign in with your ' + this.reporterRole + ' account to submit a report.';
                return;
            }

            this.submitting = true;
            try {
                const response = await fetch('/api/bug-reports', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        reporter_user_id: Number(userId),
                        issue_type: this.form.issue_type,
                        subject: this.form.subject.trim(),
                        description: this.form.description.trim()
                    })
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.detail || 'Unable to submit the report.');

                this.successMessage = `Report #${result.report_id} was sent to the LearnSync admin team.`;
                this.form = { issue_type: '', subject: '', description: '' };
            } catch (error) {
                this.errorMessage = error.message || 'Unable to submit the report.';
            } finally {
                this.submitting = false;
            }
        }
    };
}
