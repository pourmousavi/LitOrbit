import { configureBox } from 'scholarlib/services/storage/box'
import { configureDropbox } from 'scholarlib/services/storage/dropbox'

export function initScholarLib() {
  configureBox({
    clientId: import.meta.env.VITE_BOX_CLIENT_ID,
    redirectUri: import.meta.env.VITE_BOX_REDIRECT_URI,
  })
  configureDropbox({
    appKey: import.meta.env.VITE_DROPBOX_APP_KEY,
    redirectUri: import.meta.env.VITE_DROPBOX_REDIRECT_URI,
  })
}

export { LibraryService } from 'scholarlib/services/library'
export { BoxAdapter } from 'scholarlib/services/storage/box'
export { DropboxAdapter } from 'scholarlib/services/storage/dropbox'
export { createStorageAdapter } from 'scholarlib/services/storage/factory'
