/* Test-runtime boundary: literal loopback only. Never loaded by npm installation. */
'use strict';
const net = require('node:net');
const fs = require('node:fs');
function denied() {
  if (process.env.FOODFLOW_NETWORK_AUDIT) fs.appendFileSync(process.env.FOODFLOW_NETWORK_AUDIT,
    JSON.stringify({at:new Date().toISOString(),event:'non_loopback_connection_blocked'})+'\n');
  throw new Error('FoodFlow local validation permits literal loopback only');
}
const connect = net.Socket.prototype.connect;
net.Socket.prototype.connect = function (...args) {
  const options = (Array.isArray(args[0]) ? args[0] : net._normalizeArgs(args))[0];
  if (options.path || !['127.0.0.1','::1'].includes(options.host || 'localhost')) denied();
  return connect.apply(this,args);
};
