import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useEffect, useState } from 'react'
import CallChip from './rb/CallChip.jsx'

const LOOP = 8.5
const MISSION = "Brief me on this week's announcements and tell me my latest grades."
const CHAPTERS: [number, string][] = [[0, 'Mission'], [1.3, 'Warrant'], [3.3, 'Run'], [5, 'Blocked'], [6.2, 'Result']]
const CHIP = {
  size: 32, radius: 3, surfaceColor: '#fff', color: '#141518', progressColor: '#141518',
  doneColor: '#1F7A4D', errorColor: '#B27700', showTimer: false, expectedMs: 700,
}

/** A short scripted loop of the product flow, using the demo portal's real content. */
export function Preview() {
  const reduce = useReducedMotion()
  const [t, setT] = useState(reduce ? LOOP - 0.1 : 0)

  useEffect(() => {
    if (reduce) return
    let raf = 0
    let start = performance.now()
    const tick = (now: number) => {
      let s = (now - start) / 1000
      if (s > LOOP) { start = now; s = 0 }
      setT(s)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [reduce])

  const typed = MISSION.slice(0, Math.floor((Math.min(t, 1.1) / 1.1) * MISSION.length))
  const removed = t > 2.1
  const approved = t > 2.8
  const running = t > 3.3
  const chip1 = t < 3.5 ? 'idle' : t < 4.2 ? 'running' : 'done'
  const chip2 = t < 4.3 ? 'idle' : t < 5 ? 'running' : 'error'
  const blocked = t > 5
  const result = t > 6.2
  const chapter = CHAPTERS.reduce((acc, c, i) => (t >= c[0] ? i : acc), 0)

  return (
    <figure className="preview">
      <div className="win">
        <div className="win-bar"><i /><i /><i /><span className="mono">warrant / announcements and grades</span></div>
        <div className="win-body">
          <div className="pv-left">
            <span className="label">Mission</span>
            <p className="pv-mission">{typed}<span className={t < 1.2 ? 'caret' : 'caret off'} /></p>
            <AnimatePresence>
              {t > 1.3 && (
                <motion.div className={`pv-card ${approved ? 'ok' : ''}`} key="w"
                  initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                  transition={{ duration: 0.3 }}>
                  <div className="pv-card-h">
                    <span className="label">Warrant drafted by Nemotron</span>
                    {approved && <motion.span className="stamp" initial={{ scale: 1.5, opacity: 0, rotate: -6 }}
                      animate={{ scale: 1, opacity: 1, rotate: -2 }} transition={{ duration: 0.18 }}>Approved</motion.span>}
                  </div>
                  <div className="pv-line"><span className="sq" />Read announcements on the course portal</div>
                  <div className={`pv-line ${removed ? 'gone' : ''}`}>
                    <span className="sq" /><span>Read your grades on the course portal</span>
                    {!removed && t > 1.7 && <span className="pv-remove">Remove</span>}
                  </div>
                  <div className="pv-line dim"><span className="sq o" />No other websites. No posting.</div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
          <div className="pv-right">
            <span className="label">Live run</span>
            <div className="pv-chips">
              {running ? <>
                <CallChip {...CHIP} icon="file" name="open" argument="/announcements" status={chip1} />
                {t > 4.25 && <CallChip {...CHIP} icon="file" name="open" argument="/grades" status={chip2} />}
              </> : <span className="pv-wait">Waiting for approval</span>}
            </div>
            <AnimatePresence>
              {blocked && (
                <motion.div className="pv-block" key="b" initial={{ opacity: 0, y: -8, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0 }} transition={{ type: 'spring', stiffness: 420, damping: 28 }}>
                  <b>Blocked</b> GET /grades<small>Not in this mission's warrant</small>
                </motion.div>
              )}
              {result && (
                <motion.div className="pv-result" key="r" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                  <span className="label">Result</span>
                  <p><b>CS301 midterm</b> moved to Hall B, Thu 10:00. <b>Lab 4</b> now due Fri 23:59.</p>
                  <small>Grades not checked: outside the warrant.</small>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
        <div className="pv-progress" aria-hidden="true">
          {CHAPTERS.map(([, name], i) => <span key={name} className={i === chapter ? 'on' : i < chapter ? 'past' : ''}>{name}</span>)}
          <i style={{ transform: `scaleX(${t / LOOP})` }} />
        </div>
      </div>
      <figcaption className="mono">Illustrative animation. The same block happens for real in the live demo.</figcaption>
    </figure>
  )
}
