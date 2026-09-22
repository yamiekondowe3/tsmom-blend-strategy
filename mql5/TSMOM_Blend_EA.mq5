//+------------------------------------------------------------------+
//| TSMOM_Blend_EA.mq5                                               |
//| Book B -- time-series momentum on XAUUSD + BTCUSD, H4.           |
//|                                                                  |
//| Mirrors src/book_b.py exactly. Every constant here was measured  |
//| in Python (bars per day differs per symbol: gold trades ~5.13    |
//| H4 bars a day, BTC ~4.18, so the lookbacks are NOT the same bar  |
//| counts on both sleeves).                                         |
//|                                                                  |
//| Specification:                                                   |
//|   slow  = sign of trailing 60-trading-day return                 |
//|   fast  = sign of trailing 10-trading-day return                 |
//|   pos   = 0.5*slow + 0.5*fast, long-only                         |
//|   filter= flat when 20d realised vol is in its trailing 2y top   |
//|           decile                                                 |
//|   size  = inverse 20d realised vol, 15% annual target, 3x cap    |
//|   kill  = aggregate realised vol above its trailing 95th pctile  |
//|           flattens everything (section 6, portfolio level)       |
//|   exec  = signal read from the LAST CLOSED bar, position held    |
//|           from the current bar -- the one-bar lag the Python     |
//|           backtest applies as pos.shift(1)                       |
//|                                                                  |
//| SAFETY: refuses to trade outside the Strategy Tester unless      |
//| AllowLiveTrading is explicitly set true. The project brief bars  |
//| live or demo execution until build step 8.                       |
//+------------------------------------------------------------------+
#property copyright "Book B"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

//--- per-sleeve configuration -------------------------------------------------
input string  Sleeve1Symbol      = "XAUUSD";
input int     Sleeve1SlowBars    = 308;   // 60 trading days at 5.1306 bars/day
input int     Sleeve1FastBars    = 51;    // 10 trading days
input int     Sleeve1VolWindow   = 103;   // 20 trading days
input int     Sleeve1RegimeLB    = 2586;  // 2 years
input double  Sleeve1PeriodsYear = 1584.1;

input string  Sleeve2Symbol      = "BTCUSD";
input int     Sleeve2SlowBars    = 251;   // 60 trading days at 4.1834 bars/day
input int     Sleeve2FastBars    = 42;    // 10 trading days
input int     Sleeve2VolWindow   = 84;    // 20 trading days
input int     Sleeve2RegimeLB    = 2108;  // 2 years
input double  Sleeve2PeriodsYear = 1508.3;

input double  VolTarget          = 0.15;  // annualised
input double  MaxLeverage        = 3.0;
input double  RegimeDecile       = 0.90;
input double  KillPercentile     = 0.95;
input bool    UseKillSwitch      = true;
// Measured on the UNION grid of both sleeves (5.4042 bars/day), not on either
// symbol's own calendar: 20 days = 108 bars, 2 years = 2724 bars.
input int     KillVolWindow      = 108;
input int     KillLookback       = 2724;
input bool    UseDirectionalFilt = true;
input double  SleeveAllocation   = 0.5;   // equal weight
input double  MinLotChange       = 0.0;   // 0 = use the symbol's lot step
input bool    DumpParity         = true;  // write per-bar state for the parity test
input string  ParityFile         = "tsmom_parity_ea.csv";
input bool    AllowLiveTrading    = false; // MUST stay false until build step 8
input ulong   MagicNumber        = 20260922;

CTrade  trade;

struct Sleeve
  {
   string            symbol;
   int               slow, fast, volwin, regimelb;
   double            ppy;
   datetime          last_bar;
  };

Sleeve  g_sleeve[2];
int     g_count = 2;
bool    g_blocked = false;

//+------------------------------------------------------------------+
int OnInit()
  {
   g_sleeve[0].symbol=Sleeve1Symbol; g_sleeve[0].slow=Sleeve1SlowBars;
   g_sleeve[0].fast=Sleeve1FastBars; g_sleeve[0].volwin=Sleeve1VolWindow;
   g_sleeve[0].regimelb=Sleeve1RegimeLB; g_sleeve[0].ppy=Sleeve1PeriodsYear;
   g_sleeve[0].last_bar=0;

   g_sleeve[1].symbol=Sleeve2Symbol; g_sleeve[1].slow=Sleeve2SlowBars;
   g_sleeve[1].fast=Sleeve2FastBars; g_sleeve[1].volwin=Sleeve2VolWindow;
   g_sleeve[1].regimelb=Sleeve2RegimeLB; g_sleeve[1].ppy=Sleeve2PeriodsYear;
   g_sleeve[1].last_bar=0;

   // Refuse to run live/demo before build step 8. Being attached to a chart by
   // accident must not place an order.
   g_blocked = (!MQLInfoInteger(MQL_TESTER) && !AllowLiveTrading);
   if(g_blocked)
      Print("TSMOM_Blend_EA: NOT trading. Outside Strategy Tester and ",
            "AllowLiveTrading=false. This is the brief's section 2 rule.");

   // Hard block on a REAL account, independent of AllowLiveTrading. Only demo
   // execution has been authorised (build step 8), and a preset file carrying
   // AllowLiveTrading=true must not be able to reach live money just because it
   // was opened on the wrong terminal. Nothing in this project has been
   // validated on live spreads or live fills.
   if(!MQLInfoInteger(MQL_TESTER) &&
      AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_REAL)
     {
      g_blocked=true;
      Alert("TSMOM_Blend_EA: REAL account detected. Refusing to trade. ",
            "Only demo execution is authorised.");
      Print("TSMOM_Blend_EA: REAL account -- trading blocked by design.");
     }

   for(int i=0;i<g_count;i++)
      if(!SymbolSelect(g_sleeve[i].symbol,true))
        { Print("cannot select ",g_sleeve[i].symbol); return(INIT_FAILED); }

   trade.SetExpertMagicNumber(MagicNumber);
   if(DumpParity) ParityHeader();
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| sample standard deviation (ddof = 1), matching pandas .std()      |
//+------------------------------------------------------------------+
double StdDev(const double &v[], int start, int n)
  {
   if(n<2) return(0.0);
   double s=0.0;
   for(int i=0;i<n;i++) s+=v[start+i];
   double m=s/n, acc=0.0;
   for(int i=0;i<n;i++) { double d=v[start+i]-m; acc+=d*d; }
   return(MathSqrt(acc/(n-1)));
  }

//+------------------------------------------------------------------+
//| Prefix sums, so a rolling standard deviation costs O(1) per       |
//| window instead of O(window).                                      |
//|                                                                   |
//| This is not premature optimisation: the regime filter needs the   |
//| std of every one of ~2,586 trailing windows on every bar. Done    |
//| directly that is ~266k operations per bar per sleeve, and about   |
//| 6 billion across a tester run over the full history -- the test   |
//| would not finish. With prefix sums it is ~2,586.                  |
//+------------------------------------------------------------------+
void BuildPrefix(const double &v[], int n, double &ps[], double &pss[])
  {
   ArrayResize(ps,n+1); ArrayResize(pss,n+1);
   ps[0]=0.0; pss[0]=0.0;
   for(int i=0;i<n;i++)
     {
      ps[i+1]  = ps[i]  + v[i];
      pss[i+1] = pss[i] + v[i]*v[i];
     }
  }

// Sample std (ddof=1) of v[start .. start+len-1] from prefix sums.
double StdFromPrefix(const double &ps[], const double &pss[], int start, int len)
  {
   if(len<2) return(0.0);
   double s  = ps[start+len]  - ps[start];
   double ss = pss[start+len] - pss[start];
   double var = (ss - s*s/len)/(len-1);
   if(var<=0.0) return(0.0);
   return(MathSqrt(var));
  }

//+------------------------------------------------------------------+
//| Linear-interpolated quantile, matching pandas' default.           |
//| pandas uses idx = q*(n-1) then interpolates between neighbours;   |
//| a nearest-rank quantile would shift the regime threshold and make |
//| the filter fire on different bars.                                |
//+------------------------------------------------------------------+
double Quantile(double &v[], int n, double q)
  {
   if(n<=0) return(0.0);
   ArraySort(v);                    // ascending, in place
   if(n==1) return(v[0]);
   double pos=q*(n-1);
   int lo=(int)MathFloor(pos), hi=(int)MathCeil(pos);
   if(lo==hi) return(v[lo]);
   return(v[lo]+(v[hi]-v[lo])*(pos-lo));
  }

//+------------------------------------------------------------------+
//| Target weight for one sleeve, computed from CLOSED bars only.     |
//| Returns the fraction of equity to hold (>=0, long-only).          |
//| Mirrors book_b.run(): blend -> directional filter -> vol regime   |
//| -> vol target -> long-only -> one-bar lag.                        |
//+------------------------------------------------------------------+
double SleeveWeight(const Sleeve &s, double &out_slow, double &out_fast,
                    double &out_rv, double &out_thr, bool &out_flat,
                    double &out_scale, double &out_raw)
  {
   out_slow=0; out_fast=0; out_rv=0; out_thr=0; out_flat=false; out_scale=0; out_raw=0;

   // Bars needed: the longest lookback plus the regime history behind it.
   int need = s.regimelb + s.volwin + s.slow + 5;
   double close[];
   ArraySetAsSeries(close,true);
   int got = CopyClose(s.symbol, PERIOD_H4, 1, need, close);   // index 1 = last CLOSED bar
   if(got < s.slow+2) return(0.0);

   // --- signals: sign of trailing return over slow / fast lookbacks ---
   double c0 = close[0];                                   // last closed bar
   double slow_sig = (got > s.slow) ? Sign(c0/close[s.slow]-1.0) : 0.0;
   double fast_sig = (got > s.fast) ? Sign(c0/close[s.fast]-1.0) : 0.0;
   out_slow=slow_sig; out_fast=fast_sig;

   double pos = 0.5*slow_sig + 0.5*fast_sig;

   // --- directional filter: longs only above the slow moving average ---
   if(UseDirectionalFilt)
     {
      if(got > s.slow)
        {
         double sum=0.0;
         for(int i=0;i<s.slow;i++) sum+=close[i];
         double ma=sum/s.slow;
         double allow=Sign(c0-ma);
         if(Sign(pos)!=allow) pos=0.0;
        }
     }

   // --- returns series, oldest-first, for the volatility calculations ---
   int n = got;
   double ret[];
   ArrayResize(ret,n-1);
   // close[] is series-ordered (0 = newest); build chronological returns
   for(int i=0;i<n-1;i++)
     {
      double prev=close[n-1-i], cur=close[n-2-i];
      ret[i] = (prev!=0.0) ? cur/prev-1.0 : 0.0;
     }
   int rn = n-1;                       // ret[rn-1] is the most recent return

   if(rn < s.volwin) return(0.0);

   double ps[],pss[];
   BuildPrefix(ret,rn,ps,pss);

   // realised vol over the trailing vol window, ending at the last closed bar
   double rv_now = StdFromPrefix(ps,pss,rn-s.volwin,s.volwin);
   out_rv=rv_now;

   // --- regime filter: is rv in its own trailing top decile? ---
   if(rn >= s.volwin*3)
     {
      int hist_n = MathMin(s.regimelb, rn-s.volwin+1);
      if(hist_n >= s.volwin*3)
        {
         double rvs[];
         ArrayResize(rvs,hist_n);
         for(int k=0;k<hist_n;k++)
            rvs[k]=StdFromPrefix(ps,pss,rn-s.volwin-k,s.volwin);
         double thr=Quantile(rvs,hist_n,RegimeDecile);
         out_thr=thr;
         if(rv_now>thr) { out_flat=true; pos=0.0; }
        }
     }

   // --- volatility targeting ---
   double rv_ann = rv_now*MathSqrt(s.ppy);
   double scale = (rv_ann>0.0) ? VolTarget/rv_ann : 0.0;
   if(scale>MaxLeverage) scale=MaxLeverage;
   out_scale=scale;
   pos *= scale;

   if(pos<0.0) pos=0.0;                       // long-only
   if(pos>MaxLeverage) pos=MaxLeverage;
   out_raw=pos;
   return(pos);
  }

double Sign(double x) { return(x>0.0?1.0:(x<0.0?-1.0:0.0)); }

//+------------------------------------------------------------------+
//| Portfolio kill switch (brief section 6).                          |
//|                                                                   |
//| Aggregate realised volatility of an equal-weighted basket of the  |
//| TRADED MARKETS, above its trailing 95th percentile, flattens the  |
//| book.                                                             |
//|                                                                   |
//| Two design points, both settled by measurement in                 |
//| src/kill_switch_variants.py rather than by convenience:           |
//|                                                                   |
//| 1. MARKET returns, not book returns. Defining it on the           |
//|    portfolio's own strategy returns is closer to the original     |
//|    implementation, but an EA cannot compute that without either   |
//|    rebuilding every sleeve's weight history on every bar (O(n^2)) |
//|    or accumulating two years of its own returns before the        |
//|    trigger works at all. The two definitions agree on 90% of bars |
//|    and give full-period Sharpe 1.696 vs 1.682 with identical max  |
//|    drawdown, so the implementable one costs nothing.              |
//|                                                                   |
//| 2. UNION of the two symbols' timestamps, with a market that is    |
//|    shut contributing a zero return -- exactly what Python does.   |
//|    The previous version paired the two arrays POSITIONALLY, which |
//|    compares Saturday bitcoin against Friday gold, because gold    |
//|    has no weekend bars and bitcoin does.                          |
//+------------------------------------------------------------------+
bool KillSwitchActive()
  {
   if(!UseKillSwitch) return(false);
   int volwin = KillVolWindow;
   int lb     = KillLookback;
   int need   = lb+volwin+64;

   MqlRates r0[],r1[];
   ArraySetAsSeries(r0,false); ArraySetAsSeries(r1,false);
   int n0=CopyRates(g_sleeve[0].symbol,PERIOD_H4,1,need,r0);
   int n1=CopyRates(g_sleeve[1].symbol,PERIOD_H4,1,need,r1);
   if(n0<volwin*4 || n1<volwin*4) return(false);

   // Per-symbol chronological returns, each against its OWN previous bar.
   double v0[],v1[]; datetime t0[],t1[];
   ArrayResize(v0,n0-1); ArrayResize(t0,n0-1);
   ArrayResize(v1,n1-1); ArrayResize(t1,n1-1);
   for(int i=1;i<n0;i++)
     { v0[i-1]=(r0[i-1].close!=0.0)?r0[i].close/r0[i-1].close-1.0:0.0; t0[i-1]=r0[i].time; }
   for(int i=1;i<n1;i++)
     { v1[i-1]=(r1[i-1].close!=0.0)?r1[i].close/r1[i-1].close-1.0:0.0; t1[i-1]=r1[i].time; }

   // Merge onto the union of timestamps; a shut market contributes zero.
   double comb[];
   ArrayResize(comb,(n0-1)+(n1-1));
   int a=0,b=0,cn=0;
   while(a<n0-1 || b<n1-1)
     {
      double x=0.0,y=0.0;
      if(a<n0-1 && (b>=n1-1 || t0[a]<t1[b]))      { x=v0[a]; a++; }
      else if(b<n1-1 && (a>=n0-1 || t1[b]<t0[a])) { y=v1[b]; b++; }
      else                                        { x=v0[a]; y=v1[b]; a++; b++; }
      comb[cn++]=0.5*(x+y);
     }
   ArrayResize(comb,cn);
   if(cn<volwin*4) return(false);
   double ps[],pss[];
   BuildPrefix(comb,cn,ps,pss);
   double rv_now=StdFromPrefix(ps,pss,cn-volwin,volwin);
   int hist_n=MathMin(lb,cn-volwin+1);
   if(hist_n<volwin*3) return(false);
   double rvs[];
   ArrayResize(rvs,hist_n);
   for(int k=0;k<hist_n;k++)
      rvs[k]=StdFromPrefix(ps,pss,cn-volwin-k,volwin);
   return(rv_now > Quantile(rvs,hist_n,KillPercentile));
  }

//+------------------------------------------------------------------+
double TargetLots(const string sym, double weight)
  {
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   double price =SymbolInfoDouble(sym,SYMBOL_ASK);
   double cs    =SymbolInfoDouble(sym,SYMBOL_TRADE_CONTRACT_SIZE);
   if(price<=0.0 || cs<=0.0) return(0.0);
   double notional=weight*SleeveAllocation*equity;
   double lots=notional/(price*cs);

   double step=SymbolInfoDouble(sym,SYMBOL_VOLUME_STEP);
   double minl=SymbolInfoDouble(sym,SYMBOL_VOLUME_MIN);
   double maxl=SymbolInfoDouble(sym,SYMBOL_VOLUME_MAX);
   if(step>0.0) lots=MathFloor(lots/step)*step;
   if(lots<minl) lots=0.0;              // below the minimum: hold nothing
   if(lots>maxl) lots=maxl;
   return(lots);
  }

//+------------------------------------------------------------------+
//| NET lots across ALL of this EA's positions in `sym`.              |
//|                                                                   |
//| This account is in HEDGING mode, where every Buy opens a SEPARATE  |
//| position instead of adding to the existing one. Reading only the   |
//| first position made the EA think it was flat and buy again on      |
//| every bar: the first tester run stacked dozens of positions, hit   |
//| a margin stop out on 13% of the interval, and ended with 11,538    |
//| of a 100,000 deposit. The Python model holds ONE net exposure, so  |
//| the EA has to aggregate to match it.                               |
//+------------------------------------------------------------------+
double CurrentLots(const string sym)
  {
   double net=0.0;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong tk=PositionGetTicket(i);
      if(tk==0) continue;
      if(PositionGetString(POSITION_SYMBOL)!=sym) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=(long)MagicNumber) continue;
      double v=PositionGetDouble(POSITION_VOLUME);
      net += (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY) ? v : -v;
     }
   return(net);
  }

//+------------------------------------------------------------------+
//| Reduce net long exposure by `amount` lots, closing positions       |
//| (partially if needed) oldest-first. Required on a hedging account: |
//| a Sell would open an opposing position rather than reduce.         |
//+------------------------------------------------------------------+
void ReduceLong(const string sym,double amount)
  {
   double left=amount;
   for(int i=PositionsTotal()-1;i>=0 && left>1e-12;i--)
     {
      ulong tk=PositionGetTicket(i);
      if(tk==0) continue;
      if(PositionGetString(POSITION_SYMBOL)!=sym) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=(long)MagicNumber) continue;
      if(PositionGetInteger(POSITION_TYPE)!=POSITION_TYPE_BUY) continue;
      double v=PositionGetDouble(POSITION_VOLUME);
      if(v<=left+1e-12) { if(trade.PositionClose(tk)) left-=v; }
      else
        {
         double step=SymbolInfoDouble(sym,SYMBOL_VOLUME_STEP);
         double part=(step>0.0)?MathFloor(left/step)*step:left;
         if(part>0.0 && trade.PositionClosePartial(tk,part)) left-=part;
         else break;
        }
     }
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   bool killed = KillSwitchActive();

   for(int i=0;i<g_count;i++)
     {
      datetime bt=(datetime)SeriesInfoInteger(g_sleeve[i].symbol,PERIOD_H4,SERIES_LASTBAR_DATE);
      if(bt==g_sleeve[i].last_bar) continue;      // act once per new H4 bar
      g_sleeve[i].last_bar=bt;

      double sl,fs,rv,thr,scale,raw; bool flat;
      double w=SleeveWeight(g_sleeve[i],sl,fs,rv,thr,flat,scale,raw);
      if(killed) w=0.0;

      if(DumpParity)
         ParityRow(bt,g_sleeve[i].symbol,sl,fs,rv,thr,flat,scale,raw,killed,w);

      if(g_blocked) continue;

      double target=TargetLots(g_sleeve[i].symbol,w);
      double cur=CurrentLots(g_sleeve[i].symbol);

      // Live decision log. In the tester this would print a quarter of a
      // million lines, so it is limited to live/demo running, where the
      // Experts log is the only durable record of why a position was or was
      // not taken. `want` below min lot is the expected, safe outcome on a
      // small account -- not an error -- and is logged so it is visible.
      if(!MQLInfoInteger(MQL_TESTER))
        {
         double minlot=SymbolInfoDouble(g_sleeve[i].symbol,SYMBOL_VOLUME_MIN);
         double px=SymbolInfoDouble(g_sleeve[i].symbol,SYMBOL_ASK);
         double csz=SymbolInfoDouble(g_sleeve[i].symbol,SYMBOL_TRADE_CONTRACT_SIZE);
         double want=(px>0&&csz>0)?(w*SleeveAllocation*AccountInfoDouble(ACCOUNT_EQUITY))/(px*csz):0.0;
         PrintFormat("%s %s | slow %.0f fast %.0f | flat %s | scale %.3f | w %.4f "
                     "| killed %s | want %.4f lots -> target %.2f (have %.2f, min %.2f)",
                     TimeToString(bt,TIME_DATE|TIME_MINUTES), g_sleeve[i].symbol,
                     sl, fs, (flat?"Y":"N"), scale, w, (killed?"Y":"N"),
                     want, target, cur, minlot);
         if(want>0.0 && target<=0.0)
            PrintFormat("   %s: target weight %.4f is below the minimum lot at this "
                        "equity -- holding nothing. Needs equity >= %.0f.",
                        g_sleeve[i].symbol, w,
                        (w>0.0? minlot*csz*px/(w*SleeveAllocation) : 0.0));
        }
      double step=SymbolInfoDouble(g_sleeve[i].symbol,SYMBOL_VOLUME_STEP);
      double tol=(MinLotChange>0.0)?MinLotChange:step;
      if(MathAbs(target-cur)<tol-1e-12) continue;

      if(target>cur)       trade.Buy(target-cur,g_sleeve[i].symbol);
      else if(target<cur)  ReduceLong(g_sleeve[i].symbol,cur-target);
     }
  }

//+------------------------------------------------------------------+
//| Parity dump. FILE_COMMON so the tester's agent writes somewhere   |
//| the Python side can actually find.                                |
//+------------------------------------------------------------------+
// Rows are buffered and written once at the end. Reopening the file on every
// bar costs more than the strategy logic does across a full-history run.
string g_rows[];
int    g_nrows=0;

void ParityHeader()
  {
   ArrayResize(g_rows,100000);
   g_nrows=0;
  }

void ParityRow(datetime bt,string sym,double sl,double fs,double rv,double thr,
               bool flat,double scale,double raw,bool killed,double w)
  {
   if(g_nrows>=ArraySize(g_rows)) ArrayResize(g_rows,ArraySize(g_rows)+50000);
   g_rows[g_nrows++]=TimeToString(bt,TIME_DATE|TIME_MINUTES)+","+sym+","+
      DoubleToString(sl,0)+","+DoubleToString(fs,0)+","+
      DoubleToString(rv,10)+","+DoubleToString(thr,10)+","+
      (flat?"1":"0")+","+DoubleToString(scale,8)+","+DoubleToString(raw,8)+","+
      (killed?"1":"0")+","+DoubleToString(w,8);
  }

void ParityFlush()
  {
   if(!DumpParity || g_nrows<=0) return;
   int h=FileOpen(ParityFile,FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(h==INVALID_HANDLE) { Print("parity file open failed ",GetLastError()); return; }
   FileWrite(h,"bar_time,symbol,slow_sig,fast_sig,rv,thr,regime_flat,vol_scale,pos_raw,killed,target_w");
   for(int i=0;i<g_nrows;i++) FileWrite(h,g_rows[i]);
   FileClose(h);
   Print("parity rows written: ",g_nrows);
  }

void OnDeinit(const int reason) { ParityFlush(); }
//+------------------------------------------------------------------+
