import { useState, useEffect } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { TerminalUI } from './components/TerminalUI';
import { Video, Play, FileText, X, Clock } from 'lucide-react';
import './App.css';

interface ClipResult {
  videoUrl: string;
  srtUrl: string;
  fileName: string;
  srtName: string;
  duration: string;
  videoTitle: string;
  topic: string;
  aspectRatio: string;
  start: number;
  end: number;
}

function App() {
  const [wsUrl, setWsUrl] = useState<string | null>(null);
  const { subscribe, notifyListeners } = useWebSocket(wsUrl);

  const [url, setUrl] = useState('');
  const [ratio, setRatio] = useState('9:16');
  const [duration, setDuration] = useState('');
  const [count, setCount] = useState('');
  const [prompt, setPrompt] = useState('');
  const [timestamps, setTimestamps] = useState('');
  const [errors, setErrors] = useState<{ [k: string]: string }>({});
  const [isProcessing, setIsProcessing] = useState(false);
  const [results, setResults] = useState<ClipResult[]>([]);
  const [activeVideo, setActiveVideo] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<number>(0);

  useEffect(() => {
    const unsub = subscribe((data: string) => {
      try {
        const parsed = JSON.parse(data.trim());
        if (parsed.status === 'success' && parsed.output_files && parsed.output_files.length > 0) {
           const files: string[] = parsed.output_files;
           const videos = files.filter(f => f.endsWith('.mp4'));
           const srts = files.filter(f => f.endsWith('.srt'));
           const originalTitle = (parsed.video_path || '').split(/[/\\]/).pop()?.replace(/\.[^/.]+$/, "") || 'Video Klip';
           
           // Get clips metadata if available
           const clipsMetadata = parsed.clips_metadata || [];
           
           const paired = videos.map((vid, idx) => {
               const getMediaUrl = (pathStr: string) => {
                  const parts = pathStr.replace(/\\/g, '/').split('/output/');
                  if (parts.length > 1) {
                      return `http://localhost:8000/media/${parts[1]}`;
                  }
                  return pathStr; // Fallback
               };
               
               const baseName = vid.replace('.mp4', '');
               const srt = srts.find(s => s.replace('.srt', '') === baseName);

               let durationStr = '-';
               const durMatch = vid.match(/_target_(\d+)s_/);
               if (durMatch) {
                   durationStr = `${durMatch[1]}s`;
               } else {
                   const tsMatch = vid.match(/timestamp_(\d+)s_to_(\d+)s/);
                   if (tsMatch) {
                       durationStr = `${parseInt(tsMatch[2]) - parseInt(tsMatch[1])}s`;
                   }
               }

               // Get topic from metadata
               const metadata = clipsMetadata.find((m: any) => m.index === idx);
               const topic = metadata?.topic || 'Video Clip';
               const aspectRatio = metadata?.aspect_ratio || '9:16';
               const start = metadata?.start ?? 0;
               const end = metadata?.end ?? 0;

               return {
                  videoUrl: getMediaUrl(vid),
                  srtUrl: srt ? getMediaUrl(srt) : '',
                  fileName: vid.split('/').pop()?.split('\\').pop() || 'video.mp4',
                  srtName: srt ? (srt.split('/').pop()?.split('\\').pop() || '') : '',
                  duration: durationStr,
                  videoTitle: originalTitle,
                  topic: topic,
                  aspectRatio: aspectRatio,
                  start,
                  end
               };
           });
           setResults(paired);
        }
      } catch (e) {
        // Not a JSON or other error, ignore
      }
    });
    return unsub;
  }, [subscribe]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // client-side validation
    const ok = validateForm();
    if (!ok) return;

    setIsProcessing(true);
    setResults([]);
    setSessionId(prev => prev + 1); // Reset terminal UI by unmounting/remounting
    
    try {
      const response = await fetch('http://localhost:8000/api/v1/process', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          url, 
          aspect_ratio: ratio, 
          target_duration: duration ? parseInt(duration, 10) : undefined, 
          output_count: count ? parseInt(count, 10) : undefined, 
          prompt_context: prompt || undefined, 
          custom_timestamps: timestamps || undefined
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      if (data.job_id) {
        setWsUrl(`ws://localhost:8000/api/v1/ws/status/${data.job_id}`);
      } else {
        notifyListeners(JSON.stringify({ status: 'ERROR', message: 'Unexpected response: No job_id returned', step: 'error' }));
      }
    } catch (error) {
      notifyListeners(JSON.stringify({ status: 'ERROR', message: `Failed to start processing: ${error instanceof Error ? error.message : String(error)}`, step: 'error' }));
    } finally {
      setIsProcessing(false);
    }
  };

  const validateTimestamps = (val: string) => {
    if (!val) return true;
    // Accept formats like MM:SS-MM:SS or HH:MM:SS-HH:MM:SS, comma separated
    const rangeRe = /^(\d{1,2}:\d{2}(?::\d{2})?)-(\d{1,2}:\d{2}(?::\d{2})?)(\s*,\s*\d{1,2}:\d{2}(?::\d{2})?-\d{1,2}:\d{2}(?::\d{2})?)*$/;
    return rangeRe.test(val.trim());
  };

  const validateForm = () => {
    const newErr: { [k: string]: string } = {};
    if (!url || url.trim() === '') {
      newErr.url = 'URL video wajib diisi.';
    }
    if (duration) {
      const d = parseInt(duration, 10);
      if (isNaN(d) || d <= 0) newErr.duration = 'Durasi harus angka positif.';
    }
    if (count) {
      const c = parseInt(count, 10);
      if (isNaN(c) || c <= 0) newErr.count = 'Jumlah keluaran harus angka positif.';
    }
    if (!validateTimestamps(timestamps)) {
      newErr.timestamps = 'Format timestamp tidak valid. Contoh: 01:20-02:00, 05:00-06:30';
    }

    setErrors(newErr);
    return Object.keys(newErr).length === 0;
  };

  const formatClipTime = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="app-container">
      {/* Left Panel: Input Form */}
      <aside className="left-panel">
        <div className="panel-header">
          <Video className="brand-icon" />
          <h1>AI Clipper</h1>
        </div>
        
        <form className="input-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="url" title="Masukkan URL video YouTube yang ingin diproses. Contoh: https://www.youtube.com/watch?v=...">URL YouTube *</label>
            <input 
              type="url" 
              id="url"
              required
              placeholder="https://www.youtube.com/watch?v=..."
              value={url}
              onChange={(e) => { const v = e.target.value; setUrl(v); if (v && v.trim() !== '') setErrors(prev => { const p = { ...prev }; delete p.url; return p; }); }}
              onBlur={() => { if (!url) setErrors(prev => ({ ...prev, url: 'URL video wajib diisi.' })); else setErrors(prev => { const p = { ...prev }; delete p.url; return p; }) }}
              title="Masukkan URL video YouTube yang akan diklip dari layanan ini."
              disabled={isProcessing}
              className={errors.url ? 'invalid' : ''}
            />
            <small className="field-helper">Masukkan URL YouTube yang valid.</small>
            {errors.url && <small className="field-error">{`* ${errors.url}`}</small>}
          </div>

          <div className="form-row">
            <div className="form-group half">
              <label htmlFor="ratio" title="Pilih rasio aspek keluaran video: vertikal untuk Reels/TikTok, horizontal untuk YouTube.">Rasio Aspek</label>
              <select id="ratio" value={ratio} onChange={(e) => setRatio(e.target.value)} disabled={isProcessing} title="Pilih rasio keluaran video">
                <option value="9:16">Vertikal (9:16)</option>
                <option value="16:9">Horizontal (16:9)</option>
              </select>
            </div>
            <div className="form-group half">
              <label htmlFor="duration" title="Durasi target klip dalam detik. Kosongkan untuk biarkan AI memilih durasi terbaik.">Durasi Target (detik)</label>
              <input 
                type="number" 
                id="duration"
                min="1"
                step="1"
                inputMode="numeric"
                pattern="\d*"
                placeholder="mis. 60"
                value={duration}
                onChange={(e) => { const raw = e.target.value; const sanitized = raw.replace(/\D/g, ''); setDuration(sanitized); if (sanitized && !isNaN(parseInt(sanitized,10)) && parseInt(sanitized,10) > 0) setErrors(prev => { const p = { ...prev }; delete p.duration; return p; }); }}
                onBlur={() => { if (duration && (isNaN(parseInt(duration,10)) || parseInt(duration,10) <= 0)) setErrors(prev => ({ ...prev, duration: 'Durasi harus angka positif.' })); else setErrors(prev => { const p = { ...prev }; delete p.duration; return p; }) }}
                title="Masukkan durasi yang Anda inginkan untuk setiap klip (dalam detik)."
                disabled={isProcessing}
                className={errors.duration ? 'invalid' : ''}
              />
              <small className="field-helper">Hanya menerima angka bulat positif (tanpa desimal).</small>
              {errors.duration && <small className="field-error">{`* ${errors.duration}`}</small>}
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="count" title="Maksimum jumlah klip yang diinginkan dari pemrosesan ini.">Maks Jumlah Klip</label>
            <input 
              type="number" 
              id="count"
              min="1"
              step="1"
              inputMode="numeric"
              pattern="\d*"
              placeholder="mis. 5"
              value={count}
              onChange={(e) => { const raw = e.target.value; const sanitized = raw.replace(/\D/g, ''); setCount(sanitized); if (sanitized && !isNaN(parseInt(sanitized,10)) && parseInt(sanitized,10) > 0) setErrors(prev => { const p = { ...prev }; delete p.count; return p; }); }}
              onBlur={() => { if (count && (isNaN(parseInt(count,10)) || parseInt(count,10) <= 0)) setErrors(prev => ({ ...prev, count: 'Jumlah keluaran harus angka positif.' })); else setErrors(prev => { const p = { ...prev }; delete p.count; return p; }) }}
              title="Batas jumlah file klip keluaran yang dihasilkan."
              disabled={isProcessing}
              className={errors.count ? 'invalid' : ''}
            />
            <small className="field-helper">Hanya menerima angka bulat positif (tanpa desimal).</small>
            {errors.count && <small className="field-error">{`* ${errors.count}`}</small>}
          </div>

          <div className="form-group">
            <label htmlFor="prompt" title="Berikan konteks singkat untuk membantu AI menemukan momen yang relevan (opsional).">Konteks AI (opsional)</label>
            <textarea 
              id="prompt"
              rows={3}
              placeholder="Contoh: Cari momen emosional, puncak narasi, atau kutipan yang kuat"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              disabled={isProcessing}
              title="Contoh: fokus pada momen emosional, kutipan menarik, atau insiden unik."
            />
          </div>

          <div className="form-group">
            <label htmlFor="timestamps" title="Masukkan rentang waktu khusus jika ingin menentukan potongan sendiri. Format: MM:SS-MM:SS, pisah multiple dengan koma.">Timestamp Kustom (opsional)</label>
            <input 
              type="text" 
              id="timestamps"
              placeholder="mis. 01:20-02:00, 05:00-06:30"
              value={timestamps}
              onChange={(e) => { const v = e.target.value; setTimestamps(v); if (validateTimestamps(v)) setErrors(prev => { const p = { ...prev }; delete p.timestamps; return p; }); }}
              onBlur={() => { if (timestamps && !validateTimestamps(timestamps)) setErrors(prev => ({ ...prev, timestamps: 'Format timestamp tidak valid.' })); else setErrors(prev => { const p = { ...prev }; delete p.timestamps; return p; }) }}
              disabled={isProcessing}
              className={errors.timestamps ? 'invalid' : ''}
            />
            <small className="field-helper">Format: MM:SS-MM:SS. Pisahkan multiple dengan koma.</small>
            {errors.timestamps && <small className="field-error">{`* ${errors.timestamps}`}</small>}
          </div>

          <button type="submit" className="btn-submit" disabled={isProcessing}>
            <Play size={18} />
            {isProcessing ? 'Mengirim...' : 'Mulai Proses'}
          </button>
        </form>
      </aside>

      {/* Right Panel: Terminal Pipeline and Results */}
      <main className="right-panel">
        
        <div className="terminal-wrapper">
          <TerminalUI key={`term-${sessionId}`} subscribe={subscribe} height="100%" />
        </div>

        <div className="results-wrapper">
          <h2 className="results-title">Hasil Kliping</h2>
          {results.length === 0 ? (
            <div className="empty-results-state">
              <p>Belum ada hasil kliping video. Silakan kirim proses baru.</p>
            </div>
          ) : (
            <div className="results-grid">
              {results.map((res, idx) => (
                <div key={idx} className="result-card" onClick={() => setActiveVideo(res.videoUrl)}>
                  <div className="result-card-header">
                    <span className="clip-number">Klip #{idx + 1}</span>
                  </div>
                  <div className="video-container" style={{ aspectRatio: res.aspectRatio.replace(':', ' / ') }}>
                    {/* Keep video element but without controls so it acts as a thumbnail */}
                    <video src={res.videoUrl} preload="metadata" />
                    <div className="play-overlay">
                      <Play size={48} fill="white" color="white" />
                    </div>
                  </div>
                  <div className="result-info">
                    <div className="topic-section">
                      <h3 className="video-topic" title={res.topic}>{res.topic}</h3>
                    </div>
                    <div className="meta-info">
                      <div className="duration-info">
                        <Clock size={14} />
                        <span>{res.duration}</span>
                      </div>
                      {res.srtName && (
                        <div className="subtitle-badge">
                          <FileText size={12} />
                          <span>Subtitle</span>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="detail-popup">
                    <div className="popup-content">
                      <p><strong>Topik:</strong> {res.topic}</p>
                      <p><strong>Durasi:</strong> {res.duration}</p>
                      <p><strong>Rentang:</strong> {formatClipTime(res.start)} - {formatClipTime(res.end)}</p>
                      <p><strong>Aspect:</strong> {res.aspectRatio}</p>
                      {res.srtName && <p><strong>Subtitle:</strong> {res.srtName}</p>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>

      {/* Video Modal Overlay */}
      {activeVideo && (
        <div className="video-modal-overlay" onClick={() => setActiveVideo(null)}>
          <div className="video-modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="btn-close-modal" onClick={() => setActiveVideo(null)}>
              <X size={24} />
            </button>
            <video 
              src={activeVideo} 
              controls 
              autoPlay 
              playsInline
              preload="metadata"
              onClick={(e) => e.stopPropagation()}
              className={`modal-video aspect-${ratio.replace(':', '-')}`} 
            />
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
