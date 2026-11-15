



from __future__ import annotations

import json


PREFIX = {
    'feed': 'Sensor feed unavailable: ',
    'evidence': 'Check sensor data: ',
    'trend': 'Cabin trend alert: ',
    'critical': 'Critical monitoring outage: ',
    'warning': 'Warning: ',
}


def speech_messages(flags: list[dict]) -> list[str]:
    """Only announce actionable reliability and environment flags, once each."""
    messages = []
    seen = set()
    for flag in flags:
        kind = flag.get('kind')
        message = str(flag.get('message', '')).strip()
        if kind not in PREFIX or not message:
            continue
        phrase = (PREFIX[kind] + message)[:240]
        if phrase not in seen:
            messages.append(phrase)
            seen.add(phrase)
    return messages


def voice_widget_html(flags: list[dict]) -> str:





    payload = json.dumps(speech_messages(flags), ensure_ascii=True).replace('<', '\\u003c')
    return '''<!DOCTYPE html><html><head><meta charset="utf-8"><style>
      body{margin:0;font-family:system-ui,-apple-system,sans-serif;color:#172b45;background:transparent}
      button{font:inherit;font-size:13px;cursor:pointer;padding:7px 12px;border:1px solid #aabbd0;border-radius:7px;background:white;color:#172b45}
      #state{margin-left:10px;font-size:12px;color:#536477}
      </style></head><body>
      <button id="toggle" type="button">Enable spoken alerts</button>
      <button id="repeat" type="button" hidden>Speak alerts</button>
      <span id="state" role="status" aria-live="polite"></span>
      <script>
      (() => {
        const alerts = __ALERTS__;
        const prefKey='blindspot_speech_enabled_v1';
        const seenKey='blindspot_spoken_alerts_v1';
        const toggle=document.getElementById('toggle');
        const repeat=document.getElementById('repeat');
        const status=document.getElementById('state');
        const available=('speechSynthesis' in window) && ('SpeechSynthesisUtterance' in window);
        const get=(key, fallback) => { try { return localStorage.getItem(key) ?? fallback; } catch (_) { return fallback; } };
        const put=(key, val) => { try { localStorage.setItem(key,val); } catch (_) { /* private contexts */ } };
        const oldSeen=() => { try { return JSON.parse(get(seenKey,'[]')); } catch (_) {return [];} };
        let speechEnabled=get(prefKey,'false')==='true';
        const refresh=()=>{
          toggle.textContent=speechEnabled?'Mute spoken alerts':'Enable spoken alerts';
          repeat.hidden=!speechEnabled || alerts.length===0;
          status.textContent=!available?'Voice unavailable in this browser':(alerts.length?alerts.length+' alert(s)':'No alerts');
        };
        const speak=(phrases)=>{
          if (!available || !speechEnabled) return;
          window.speechSynthesis.cancel();
          phrases.slice(0,3).forEach((phrase)=>{
            const utterance=new SpeechSynthesisUtterance(phrase);
            utterance.rate=1.0;
            utterance.volume=0.9;
            window.speechSynthesis.speak(utterance);
          });
        };
        toggle.addEventListener('click',()=>{
          speechEnabled=!speechEnabled;put(prefKey,String(speechEnabled));
          if (speechEnabled) { put(seenKey,JSON.stringify(alerts));speak(alerts); }
          else if (available) window.speechSynthesis.cancel();
          refresh();
        });
        repeat.addEventListener('click',()=>speak(alerts));
        refresh();
        if (speechEnabled && alerts.length && available){
          const seen=oldSeen();
          const fresh=alerts.filter(a=>!seen.includes(a));
          if(fresh.length) speak(fresh);
          put(seenKey,JSON.stringify(alerts));
        } else if (speechEnabled) { put(seenKey,JSON.stringify(alerts)); }
      })();
      </script></body></html>'''.replace('__ALERTS__', payload)
