import { useScholarLibStore } from '@/stores/scholarLibStore'
import FolderSelect from '@/components/integrations/FolderSelect'

export default function IntegrationsTab() {
  const status = useScholarLibStore((s) => s.status)
  const provider = useScholarLibStore((s) => s.provider)
  const folders = useScholarLibStore((s) => s.folders)
  const defaultFolderId = useScholarLibStore((s) => s.defaultFolderId)
  const connect = useScholarLibStore((s) => s.connect)
  const disconnect = useScholarLibStore((s) => s.disconnect)
  const setDefaultFolder = useScholarLibStore((s) => s.setDefaultFolder)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div
        className="rounded-2xl border border-border-default bg-bg-surface"
        style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}
      >
        <h2
          className="font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase"
          style={{ marginBottom: 0 }}
        >
          ScholarLib Connection
        </h2>

        <p className="font-mono text-xs text-text-tertiary" style={{ lineHeight: 1.6 }}>
          Connect LitOrbit to your ScholarLib library to save papers for long-term reference, annotation, and AI chat.
        </p>

        {status === 'connected' ? (
          <>
            <div
              className="rounded-xl border border-border-default bg-bg-base"
              style={{ padding: '14px 18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span
                    className="inline-flex items-center rounded-full bg-success/10 font-mono text-xs text-success"
                    style={{ gap: 6, padding: '4px 14px' }}
                  >
                    <span style={{ fontSize: 8 }}>●</span>
                    Connected ({provider === 'box' ? 'Box' : 'Dropbox'})
                  </span>
                </div>
              </div>
              <button
                onClick={disconnect}
                className="rounded-xl border border-border-default font-mono text-xs text-text-secondary transition hover:border-danger hover:text-danger"
                style={{ padding: '8px 16px' }}
              >
                Disconnect
              </button>
            </div>

            {/* Default folder picker */}
            <div>
              <label
                className="font-mono text-text-secondary"
                style={{ display: 'block', fontSize: 12, marginBottom: 8 }}
              >
                Default Folder
              </label>
              <FolderSelect folders={folders} value={defaultFolderId || ''} onChange={setDefaultFolder} />
              <p className="font-mono text-xs text-text-tertiary" style={{ marginTop: 8 }}>
                Papers will be saved to this folder unless you choose a different one when sending.
              </p>
            </div>
          </>
        ) : status === 'connecting' ? (
          <div
            className="rounded-xl border border-border-default bg-bg-base"
            style={{ padding: '20px', textAlign: 'center' }}
          >
            <span
              className="inline-flex items-center rounded-full bg-bg-elevated font-mono text-xs text-text-secondary"
              style={{ gap: 6, padding: '4px 14px' }}
            >
              <span style={{ fontSize: 8 }}>●</span>
              Connecting...
            </span>
          </div>
        ) : (
          <>
            <p className="font-mono text-xs text-text-secondary">
              Choose your storage provider:
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              {(['box', 'dropbox'] as const).map((p) => (
                <div
                  key={p}
                  className="rounded-xl border border-border-default bg-bg-base transition hover:border-accent cursor-pointer"
                  style={{ padding: 20, textAlign: 'center' }}
                  onClick={() => connect(p)}
                >
                  <p className="font-mono text-sm font-medium text-text-primary" style={{ marginBottom: 12 }}>
                    {p === 'box' ? 'Box' : 'Dropbox'}
                  </p>
                  <button
                    className="rounded-xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover"
                    style={{ padding: '10px 20px' }}
                  >
                    Connect
                  </button>
                </div>
              ))}
            </div>

            <p className="font-mono text-xs text-text-tertiary" style={{ lineHeight: 1.6 }}>
              Your ScholarLib data stays in your own cloud storage. LitOrbit never stores your files.
            </p>

            {status === 'error' && (
              <p className="font-mono text-xs text-danger">
                Connection failed. Please try again.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
}
