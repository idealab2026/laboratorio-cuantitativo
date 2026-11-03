// Read-only lot reconstruction for the public paper ledger.
// FIFO is a DISPLAY reconciliation, not an assertion of the original tax-lot method.
// Never treat holds or corporate entitlements as stock-market executions.
const positive = value => typeof value === "number" && Number.isFinite(value) && value > 0;
const validFee = value => typeof value === "number" && Number.isFinite(value) && value >= 0;
const epsilon = 1e-7;
const safeReturn = (pnl, invested) => pnl !== null && positive(invested) ? 100 * pnl / invested : null;
const goodNumber = value => typeof value === "number" && Number.isFinite(value) ? value : null;

export function buildOperationLots(track) {
 if (!track || !Array.isArray(track.sessions)) return [];
 const lots = [], positions = new Map();
 let ordinal = 0;
 const book = ticker => {
  if (!positions.has(ticker)) positions.set(ticker, []);
  return positions.get(ticker);
 };
 // Trade events and split events are sorted together, preserving the original
 // order of executed fills on a given session.
 const timeline = track.sessions.flatMap(session => (session.actions || [])
  .filter(a => ["buy", "sell", "corporate_action"].includes(a.side))
  .map((a, index) => ({date:session.date, index:index + 1, action:a, rank:1})));
 for (const s of track.splits || []) {
  if (typeof s.date === "string" && typeof s.ticker === "string" && positive(s.ratio)) {
   timeline.push({date:s.date,index:0,action:s,rank:0});
  }
 }
 timeline.sort((a,b) => a.date.localeCompare(b.date) || a.rank-b.rank || a.index-b.index);
 for (const {date,rank,action:a} of timeline) {
  const ticker = a.ticker;
  if (rank === 0) {
   for (const lot of book(ticker)) {
    if (lot.remaining > epsilon && !lot.converted) {
     lot.remaining *= a.ratio;
     lot.splitFactor *= a.ratio;
     if (positive(lot.basisUnit)) lot.basisUnit /= a.ratio;
    }
   }
   continue;
  }
  if (a.side === "buy") {
   const qty = positive(a.quantity) ? a.quantity : null;
   const price = positive(a.price) ? a.price : null;
   const buyFee = validFee(a.fee) ? a.fee : null;
   const invested = qty !== null && price !== null ? qty * price + (buyFee ?? 0) : null;
   const lot = {
    id: ticker + "_" + date + "_" + (++ordinal), ticker,
    buyDate: date, saleDate: null, entryPrice: price, lastSalePrice: null,
    quantityBought: qty, remaining: qty ?? 0, splitFactor: 1,
    boughtCost: invested, basisUnit: invested !== null ? invested / qty : null,
    saleQuantity: 0, saleNotional: 0, realised: 0, feeComplete: buyFee !== null,
    converted: false, convertedTo: null, uncertain: qty === null,
    saleEvidenceMissing: false, source: a.price_basis || "not_recorded"
   };
   lots.push(lot);
   book(ticker).push(lot);
   continue;
  }
  if (a.side === "corporate_action") {
   for (const lot of book(ticker)) {
    if (lot.remaining > epsilon) {
     lot.converted = true;
     lot.convertedTo = a.successor_ticker || null;
     lot.remaining = 0;
    }
   }
   continue;
  }
  if (a.side !== "sell") continue;
  let required = positive(a.quantity) ? a.quantity : null;
  const salePrice = positive(a.price) ? a.price : null;
  const saleFee = validFee(a.fee) ? a.fee : null;
  if (required === null) {
   for (const lot of book(ticker)) if (lot.remaining > epsilon) lot.uncertain = true;
  } else {
   for (const lot of book(ticker)) {
    if (required <= epsilon) break;
    if (lot.remaining <= epsilon || lot.converted || lot.uncertain) continue;
    const filled = Math.min(lot.remaining,required);
    const allocatedFee = saleFee === null ? 0 : saleFee * filled / a.quantity;
    if (salePrice === null || lot.basisUnit === null) {
     lot.saleEvidenceMissing = true;
    } else {
     lot.realised += filled * (salePrice - lot.basisUnit) - allocatedFee;
     lot.saleNotional += filled * salePrice;
     lot.saleQuantity += filled;
    }
    lot.feeComplete &&= saleFee !== null;
    lot.lastSalePrice = salePrice;
    lot.saleDate = date;
    lot.remaining -= filled;
    required -= filled;
    if (lot.remaining < epsilon) lot.remaining = 0;
   }
  }
  if (required === null || required > epsilon) {
   lots.push({
    id:ticker + "_unmatched_" + (++ordinal),ticker,buyDate:null,saleDate:date,
    entryPrice:null,lastSalePrice:salePrice,quantityBought:null,remaining:0,
    splitFactor:1,boughtCost:null,basisUnit:null,saleQuantity:0,saleNotional:0,
    realised:0,feeComplete:false,converted:false,convertedTo:null,uncertain:true,
    saleEvidenceMissing:true,source:"unmatched_sale"
   });
  }
 }
 const until = track.sessions.at(-1)?.date || "";
 return lots.map(lot => {
  const quotes = (track.prices?.[lot.ticker] || []).filter(q =>
   positive(q.price) && q.date >= (lot.buyDate || "") && q.date <= until);
  const close = quotes.length ? quotes.reduce((best,q) => q.date > best.date ? q : best) : null;
  const isOpen = lot.remaining > epsilon && !lot.converted;
  const isClosed = !isOpen && !lot.converted && !!lot.buyDate && lot.saleQuantity > epsilon;
  const status = lot.converted ? "convertida" :
   lot.uncertain || !lot.buyDate ? "sin_base" :
   isClosed ? "cerrada" :
   lot.saleQuantity > epsilon ? "parcial" : "abierta";
  // For open lots the retained closing quote is an observed MARK, not a sale.
  const pnl = !lot.uncertain && !lot.saleEvidenceMissing && !lot.converted &&
   lot.boughtCost !== null && (!isOpen || close !== null)
   ? lot.realised + (isOpen ? lot.remaining * (close.price - lot.basisUnit) : 0)
   : null;
  const salePrice = lot.saleQuantity > epsilon ? lot.saleNotional / lot.saleQuantity : lot.lastSalePrice;
  return {
   id:lot.id, ticker:lot.ticker, buyDate:lot.buyDate, saleDate:lot.saleDate,
   action:status, buyPrice:positive(lot.entryPrice) ? lot.entryPrice / lot.splitFactor : null,
   buyPriceOriginal:lot.entryPrice, salePrice:positive(salePrice) ? salePrice : null,
   shares:lot.quantityBought, remainingShares:isOpen ? lot.remaining : 0,
   soldShares:lot.saleQuantity, splitFactor:lot.splitFactor, invested:lot.boughtCost,
   pnl:goodNumber(pnl), returnPct:safeReturn(pnl,lot.boughtCost),
   markDate:isOpen ? close?.date || null : null,
   markPrice:isOpen ? close?.price || null : null,
   feeComplete:lot.feeComplete, convertedTo:lot.convertedTo, source:lot.source
  };
 });
}
export function sortOperationLots(rows, key="recent", descending=true) {
 const compare = (a,b) => {
  if (key === "recent") {
   const rank = x => x.action === "abierta" || x.action === "parcial" ? 0 : 1;
   return rank(a)-rank(b) ||
    String(b.buyDate || b.saleDate || "").localeCompare(String(a.buyDate || a.saleDate || "")) ||
    a.ticker.localeCompare(b.ticker);
  }
  const get = row => ({
   ticker:row.ticker, action:row.action, buyPrice:row.buyPrice,
   salePrice:row.salePrice, returnPct:row.returnPct, pnl:row.pnl,
   invested:row.invested, shares:row.shares
  })[key];
  const x=get(a),y=get(b);
  if (x === null || x === undefined) return y === null || y === undefined ? 0 : 1;
  if (y === null || y === undefined) return -1;
  const delta = typeof x === "string" ? x.localeCompare(y,"es") : x-y;
  return descending ? -delta : delta;
 };
 return [...rows].sort(compare);
}
