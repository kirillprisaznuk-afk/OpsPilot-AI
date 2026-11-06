import type { components } from './generated';
export type Principal = components['schemas']['Principal'];
export type Metric = components['schemas']['Metric'];
export type Report = Required<components['schemas']['AnalyticsReport']>;
export type Proposal = components['schemas']['ProposalOut'];
export type ProposalInput = components['schemas']['ProposalInput-Input'];
export type Task = components['schemas']['TaskOut'];
export type Escalation = components['schemas']['EscalationOut'];
export type Receipt = components['schemas']['ExecutionOut'];
export type Audit = components['schemas']['AuditOut'];
export type Source = components['schemas']['SourcePreview'];
export type Document = components['schemas']['DocumentMetadata'];
export type Citation = components['schemas']['Citation'];
export type SearchResult = components['schemas']['SearchResponse'];
export type Hybrid = Omit<
  Required<components['schemas']['HybridResponse']>,
  'evidence_graph' | 'usage'
> & {
  evidence_graph: Required<components['schemas']['Graph']>;
  usage: Required<components['schemas']['Usage']>;
};
export type Summary = components['schemas']['SummaryOut'];
export type Evidence = components['schemas']['EvidenceOut'];
export type Subject = components['schemas']['SubjectRow'];
export type Person = components['schemas']['Person'];
export type Page<T> = { items: T[]; total: number; limit: number; offset: number };
export type Session = { principal: Principal; csrf: string; expires_at: string };
export type JsonRecord = Record<string, unknown>;
