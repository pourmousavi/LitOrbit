declare module 'scholarlib/services/storage/box' {
  export function configureBox(config: { clientId: string; redirectUri: string }): void
  export class BoxAdapter {
    connect(): void
    handleCallback(code: string, state: string): Promise<void>
    disconnect(): void
    isConnected(): Promise<boolean>
    refreshTokenIfNeeded(): Promise<void>
    readJSON(path: string): Promise<any>
    writeJSON(path: string, data: any): Promise<void>
  }
}

declare module 'scholarlib/services/storage/dropbox' {
  export function configureDropbox(config: { appKey: string; redirectUri: string }): void
  export class DropboxAdapter {
    connect(): void
    handleCallback(code: string, state: string): Promise<void>
    disconnect(): void
    isConnected(): Promise<boolean>
    refreshTokenIfNeeded(): Promise<void>
    readJSON(path: string): Promise<any>
    writeJSON(path: string, data: any): Promise<void>
  }
}

declare module 'scholarlib/services/library' {
  export const LibraryService: {
    loadLibrary(adapter: any): Promise<any>
    saveLibrary(adapter: any, library: any): Promise<void>
    addDocument(adapter: any, library: any, docData: any, file: File | null): Promise<any>
    findDuplicateByDOI(library: any, doi: string): any | null
    findDuplicateByTitle(library: any, title: string): any | null
  }
}

declare module 'scholarlib/services/storage/factory' {
  export function createStorageAdapter(provider: string): any
}
