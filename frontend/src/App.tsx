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
           
           const paired = videos.map(vid => {
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

               return {
                  videoUrl: getMediaUrl(vid),
                  srtUrl: srt ? getMediaUrl(srt) : '',
                  fileName: vid.split('/').pop()?.split('\\').pop() || 'video.mp4',
                  srtName: srt ? (srt.split('/').pop()?.split('\\').pop() || '') : '',
                  duration: durationStr,
                  videoTitle: originalTitle
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
            <label htmlFor="url">YouTube URL *</label>
            <input 
              type="url" 
              id="url"
              required
              placeholder="https://www.youtube.com/watch?v=..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={isProcessing}
            />
          </div>

          <div className="form-row">
            <div className="form-group half">
              <label htmlFor="ratio">Aspect Ratio</label>
              <select id="ratio" value={ratio} onChange={(e) => setRatio(e.target.value)} disabled={isProcessing}>
                <option value="9:16">Vertical (9:16)</option>
                <option value="16:9">Horizontal (16:9)</option>
              </select>
            </div>
            <div className="form-group half">
              <label htmlFor="duration">Target Duration (sec)</label>
              <input 
                type="number" 
                id="duration"
                min="1"
                placeholder="e.g. 60"
                value={duration}
                onChange={(e) => setDuration(e.target.value)}
                disabled={isProcessing}
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="count">Max Output Clips</label>
            <input 
              type="number" 
              id="count"
              min="1"
              placeholder="e.g. 5"
              value={count}
              onChange={(e) => setCount(e.target.value)}
              disabled={isProcessing}
            />
          </div>

          <div className="form-group">
            <label htmlFor="prompt">AI Context Prompt</label>
            <textarea 
              id="prompt"
              rows={3}
              placeholder="What kind of moments are you looking for?"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              disabled={isProcessing}
            />
          </div>

          <div className="form-group">
            <label htmlFor="timestamps">Custom Timestamps (Optional)</label>
            <input 
              type="text" 
              id="timestamps"
              placeholder="e.g. 01:20-02:00, 05:00-06:30"
              value={timestamps}
              onChange={(e) => setTimestamps(e.target.value)}
              disabled={isProcessing}
            />
          </div>

          <button type="submit" className="btn-submit" disabled={!url || isProcessing}>
            <Play size={18} />
            {isProcessing ? 'Submitting...' : 'Start Processing'}
          </button>
        </form>
      </aside>

      {/* Right Panel: Terminal Pipeline and Results */}
      <main className="right-panel">
        
        <div className="terminal-wrapper">
          <TerminalUI key={`term-${sessionId}`} subscribe={subscribe} height="100%" />
        </div>

        <div className="results-wrapper">
          <h2 className="results-title">Clipping Results</h2>
          {results.length === 0 ? (
            <div className="empty-results-state">
              <p>Belum ada hasil kliping video. Silakan submit proses baru.</p>
            </div>
          ) : (
            <div className="results-grid">
              {results.map((res, idx) => (
                <div key={idx} className="result-card" onClick={() => setActiveVideo(res.videoUrl)}>
                  <div className="video-container aspect-1-1">
                    {/* Keep video element but without controls so it acts as a thumbnail */}
                    <video src={res.videoUrl} preload="metadata" />
                    <div className="play-overlay">
                      <Play size={48} fill="white" color="white" />
                    </div>
                  </div>
                  <div className="result-info">
                    <span className="detail-label">Detail Video</span>
                    <h3 title={res.videoTitle}>{res.videoTitle}</h3>
                    <div className="meta-info">
                      <div className="duration-info">
                        <Clock size={14} />
                        <span>Durasi: {res.duration}</span>
                      </div>
                      {res.srtName && (
                        <div className="subtitle-info" title={res.srtName}>
                          <FileText size={14} />
                          <span className="truncate">Sub: {res.srtName}</span>
                        </div>
                      )}
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
              className={`modal-video aspect-${ratio.replace(':', '-')}`} 
            />
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
