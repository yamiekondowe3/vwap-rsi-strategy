//+------------------------------------------------------------------+
//|                                                 VWAP_RSI_EA.mq5 |
//|   Session-anchored VWAP + RSI mean-reversion/trend-continuation |
//|   Mirrors backtest/engine.py (VWAPRSIParams) so parameters and  |
//|   entry/exit logic stay in lockstep with the Python backtest.   |
//|   NOT VALIDATED IN THE STRATEGY TESTER YET -- proof-of-concept  |
//|   code, review before any demo/live deployment.                 |
//+------------------------------------------------------------------+
#property copyright "trading-systems"
#property version   "1.00"
#property strict

input int    RSI_Period          = 14;
input double RSI_Overbought      = 70.0;
input double RSI_Oversold        = 30.0;
input int    VWAP_SlopeWindowMin = 15;    // in bars of the chart timeframe
input int    ATR_Period          = 14;
input double Stop_ATR_Mult       = 2.0;
input double Target_ATR_Mult     = 2.0;   // 1.0R default; tune per WFO results
input double Risk_Pct            = 0.5;   // percent of equity risked per trade
input int    Day_Boundary_Hour   = 0;     // UTC hour VWAP resets (0 = midnight UTC)
input double Max_Cost_Ratio    = 0.20;  // skip setups where spread exceeds this share of stop distance
input int    Slippage_Points     = 30;
input double Max_Leverage       = 50.0; // cap notional at this multiple of equity
input int    MagicNumber         = 20260904;

int rsiHandle, atrHandle;
datetime lastVwapResetDay = 0;
double vwapCumTPV = 0.0, vwapCumVol = 0.0;
double vwapHistory[]; // rolling buffer for slope check

int OnInit()
{
   rsiHandle = iRSI(_Symbol, PERIOD_CURRENT, RSI_Period, PRICE_CLOSE);
   atrHandle = iATR(_Symbol, PERIOD_CURRENT, ATR_Period);
   if(rsiHandle == INVALID_HANDLE || atrHandle == INVALID_HANDLE)
   {
      Print("Failed to create indicator handles");
      return INIT_FAILED;
   }
   ArrayResize(vwapHistory, VWAP_SlopeWindowMin + 5);
   ArrayInitialize(vwapHistory, 0.0);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   IndicatorRelease(rsiHandle);
   IndicatorRelease(atrHandle);
}

//--- Anchored VWAP: resets at Day_Boundary_Hour UTC, matches
//--- common/indicators.py::anchored_vwap's daily-reset convention.
double UpdateAndGetVWAP()
{
   datetime now = TimeCurrent();
   MqlDateTime dt;
   TimeToStruct(now, dt);
   datetime dayKey = now - (dt.hour * 3600 + dt.min * 60 + dt.sec);
   if(dt.hour < Day_Boundary_Hour) dayKey -= 86400; // align to boundary, not midnight, when offset

   if(dayKey != lastVwapResetDay)
   {
      lastVwapResetDay = dayKey;
      vwapCumTPV = 0.0;
      vwapCumVol = 0.0;
   }

   double high = iHigh(_Symbol, PERIOD_CURRENT, 1);
   double low  = iLow(_Symbol, PERIOD_CURRENT, 1);
   double close= iClose(_Symbol, PERIOD_CURRENT, 1);
   long   vol  = iVolume(_Symbol, PERIOD_CURRENT, 1); // tick volume proxy (see research docs' FX/crypto caveat)

   double typical = (high + low + close) / 3.0;
   vwapCumTPV += typical * (double)vol;
   vwapCumVol += (double)vol;

   if(vwapCumVol <= 0) return close;
   return vwapCumTPV / vwapCumVol;
}

bool VwapSlopeUp(double currentVwap)
{
   // Shift history buffer, compare against the value VWAP_SlopeWindowMin bars back.
   int n = ArraySize(vwapHistory);
   for(int i = n - 1; i > 0; i--) vwapHistory[i] = vwapHistory[i - 1];
   vwapHistory[0] = currentVwap;
   double past = vwapHistory[n - 1];
   if(past == 0.0) return false;
   return currentVwap > past;
}
bool VwapSlopeDown(double currentVwap)
{
   int n = ArraySize(vwapHistory);
   double past = vwapHistory[n - 1];
   if(past == 0.0) return false;
   return currentVwap < past;
}

bool HasOpenPosition()
{
   for(int i = 0; i < PositionsTotal(); i++)
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == MagicNumber)
         return true;
   return false;
}

//--- Fixed-fractional position sizing from ATR-based stop distance,
//--- mirroring backtest/engine.py's `size = risk_budget*equity / risk_per_unit`.

//--- Select a filling mode the SYMBOL actually supports.
//--- Both EAs previously hardcoded ORDER_FILLING_IOC. This broker reports
//--- filling_mode=1 (FOK only) on XAUUSD and BTCUSD, so every order would
//--- have been rejected with retcode 10030 "Unsupported filling mode".
//--- Found by ops_rehearsal.py via order_check() before any live deployment.
ENUM_ORDER_TYPE_FILLING PickFillingMode()
{
   long modes = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((modes & SYMBOL_FILLING_FOK) != 0) return ORDER_FILLING_FOK;
   if((modes & SYMBOL_FILLING_IOC) != 0) return ORDER_FILLING_IOC;
   return ORDER_FILLING_RETURN;
}

double CalcLotSize(double stopDistance)
{
   //--- COST GUARD (added after a real defect found in cross-sectional testing)
   //--- Size is riskAmount/stopDistance. When ATR collapses relative to the
   //--- spread (e.g. quiet Asian-session hours on low-volatility symbols),
   //--- stopDistance shrinks, size explodes, and the fixed spread on that
   //--- oversized position costs many R despite a nominal 1R stop. Backtests
   //--- showed -18R to -21R per trade from exactly this. Refuse such setups.
   double spreadPrice = (double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD)
                        * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(stopDistance <= 0) return 0.0;
   if(spreadPrice / stopDistance > Max_Cost_Ratio) return 0.0;
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskAmount = equity * (Risk_Pct / 100.0);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize <= 0 || tickValue <= 0 || stopDistance <= 0) return 0.0;
   double valuePerUnit = tickValue / tickSize; // account currency per 1.0 price unit per lot
   double lots = riskAmount / (stopDistance * valuePerUnit);

   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   //--- Second guard: cap notional so a small stop cannot imply a position
   //--- larger than the account can carry.
   double contract = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   double price    = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(contract > 0 && price > 0)
   {
      double maxLots = (Max_Leverage * equity) / (contract * price);
      lots = MathMin(lots, maxLots);
   }
   lots = MathFloor(lots / step) * step;
   //--- If the guards pushed size below the broker minimum, SKIP the trade.
   //--- Forcing it back up to minLot would silently violate the very cap that
   //--- was just applied -- the original bug in a different disguise.
   if(lots < minLot) return 0.0;
   return MathMin(maxLot, lots);
}

void OnTick()
{
   if(!IsNewBar()) return;
   if(HasOpenPosition()) return; // one position at a time, matches backtest engine

   double vwap = UpdateAndGetVWAP();
   bool slopeUp = VwapSlopeUp(vwap);
   bool slopeDown = VwapSlopeDown(vwap);

   double rsiVals[3], atrVals[2];
   if(CopyBuffer(rsiHandle, 0, 0, 3, rsiVals) < 3) return;
   if(CopyBuffer(atrHandle, 0, 0, 2, atrVals) < 2) return;
   double rsiPrev = rsiVals[2]; // bar[1] shifted; index ordering per CopyBuffer (0=most recent closed)
   double rsiNow  = rsiVals[1];
   double atrNow  = atrVals[1];
   if(atrNow <= 0) return;

   double closeNow = iClose(_Symbol, PERIOD_CURRENT, 1);

   bool longSignal  = (closeNow > vwap) && slopeUp   && (rsiPrev < RSI_Oversold)  && (rsiNow >= RSI_Oversold);
   bool shortSignal = (closeNow < vwap) && slopeDown && (rsiPrev > RSI_Overbought) && (rsiNow <= RSI_Overbought);

   if(!longSignal && !shortSignal) return;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   MqlTradeRequest req; MqlTradeResult res;
   ZeroMemory(req); ZeroMemory(res);
   req.action = TRADE_ACTION_DEAL;
   req.symbol = _Symbol;
   req.deviation = Slippage_Points;
   req.magic = MagicNumber;
   req.type_filling = PickFillingMode();

   if(longSignal)
   {
      double stop = ask - Stop_ATR_Mult * atrNow;
      double target = ask + Target_ATR_Mult * atrNow;
      double lots = CalcLotSize(ask - stop);
      if(lots <= 0) return;
      req.type = ORDER_TYPE_BUY;
      req.price = ask; req.volume = lots; req.sl = stop; req.tp = target;
      OrderSend(req, res);
   }
   else if(shortSignal)
   {
      double stop = bid + Stop_ATR_Mult * atrNow;
      double target = bid - Target_ATR_Mult * atrNow;
      double lots = CalcLotSize(stop - bid);
      if(lots <= 0) return;
      req.type = ORDER_TYPE_SELL;
      req.price = bid; req.volume = lots; req.sl = stop; req.tp = target;
      OrderSend(req, res);
   }
}

datetime lastBarTime = 0;
bool IsNewBar()
{
   datetime t = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(t != lastBarTime) { lastBarTime = t; return true; }
   return false;
}
//+------------------------------------------------------------------+
