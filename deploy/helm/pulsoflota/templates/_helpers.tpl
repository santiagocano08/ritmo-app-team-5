{{- define "pulsoflota.fullname" -}}
{{- .Release.Name | trunc 40 | trimSuffix "-" -}}
{{- end -}}

{{- define "pulsoflota.labels" -}}
app.kubernetes.io/part-of: pulsoflota
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{- define "pulsoflota.selector" -}}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{- define "pulsoflota.dbHost" -}}
{{ include "pulsoflota.fullname" . }}-db
{{- end -}}

{{- define "pulsoflota.appImage" -}}
{{ .Values.image.app.repository }}:{{ .Values.image.app.tag }}
{{- end -}}

{{/* Restricted pod security for the app images (non-root UID 10001, Constitution A02). */}}
{{- define "pulsoflota.podSecurity" -}}
runAsNonRoot: true
runAsUser: 10001
runAsGroup: 10001
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{- define "pulsoflota.containerSecurity" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: ["ALL"]
{{- end -}}

{{/* Database settings. DATABASE_URL is composed from the Secret with dependent env vars. */}}
{{- define "pulsoflota.dbEnv" -}}
- name: POSTGRES_USER
  value: {{ .Values.db.user | quote }}
- name: POSTGRES_DB
  value: {{ .Values.db.database | quote }}
- name: POSTGRES_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .Values.db.existingSecret }}
      key: POSTGRES_PASSWORD
- name: DATABASE_URL
  value: "postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@{{ include "pulsoflota.dbHost" . }}:5432/$(POSTGRES_DB)"
- name: LOG_LEVEL
  value: {{ .Values.logLevel | quote }}
- name: PYTHONPATH
  value: /app
{{- end -}}

{{/* Waits for PostgreSQL: Kubernetes has no depends_on. */}}
{{- define "pulsoflota.waitForDb" -}}
- name: wait-for-db
  image: {{ .Values.db.image }}
  command: ["sh", "-c", "until pg_isready -h {{ include "pulsoflota.dbHost" . }} -p 5432; do echo waiting for db; sleep 2; done"]
  securityContext:
    runAsNonRoot: true
    runAsUser: 999
    allowPrivilegeEscalation: false
    capabilities:
      drop: ["ALL"]
  resources:
    requests: { cpu: 10m, memory: 16Mi }
    limits: { memory: 64Mi }
{{- end -}}
