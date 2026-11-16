/* Runtime-generated metadata only. No headers, credentials, raw body or errors. */
'use strict';
const fs = require('node:fs');
function safe(value) { return typeof value === 'string' && /^[A-Za-z0-9_.:-]{1,100}$/.test(value) ? value : null; }
function project(run, workflow, executionId) {
  const data = run?.data?.resultData?.runData || {};
  const incoming = data['Webhook autenticado']?.[0]?.data?.main?.[0]?.[0]?.json?.body || {};
  const receipt = data['Persistir fila local']?.[0]?.data?.main?.[0]?.[0]?.json || {};
  const error = data['Persistir fila local']?.[0]?.error || run?.data?.resultData?.error;
  const httpCode = Number(error?.httpCode || error?.statusCode);
  return {captured_at:new Date().toISOString(),execution_id:safe(String(executionId)),
    workflow_id:safe(workflow.id),status:safe(run?.status),finished:run?.finished === true,
    event_id:safe(incoming.event_id),ticket_id:safe(incoming.ticket_id),
    record_id:safe(receipt.record_id),received:receipt.received === true,
    nodes:Object.keys(data).filter(n=>['Webhook autenticado','Persistir fila local','ACK apos commit'].includes(n)),
    error_present:!!error,http_code:Number.isInteger(httpCode) && httpCode>=100 && httpCode<=599 ? httpCode : null};
}
module.exports = {workflow:{postExecute:[async function(run,workflow,executionId) {
  if (!process.env.FOODFLOW_RUNTIME_EVIDENCE) throw new Error('Evidence destination required');
  fs.appendFileSync(process.env.FOODFLOW_RUNTIME_EVIDENCE,JSON.stringify(project(run,workflow,executionId))+'\n');
}]}};
