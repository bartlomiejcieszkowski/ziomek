/**
 * Status representing the current state of the TTS engine.
 *
 * - `idle`:     No speech is in progress.
 * - `speaking`: Speech synthesis is actively producing audio.
 * - `stopping`: A stop request has been issued and is being processed.
 * - `error`:    An unrecoverable error has occurred.
 */
export type SpeechStatus = 'idle' | 'speaking' | 'stopping' | 'error';

/**
 * Callback invoked whenever the TTS status changes.
 *
 * @param status - The new status of the TTS engine.
 */
export type TTSCallback = (status: SpeechStatus) => void;

/**
 * Abstract base class for Text-to-Speech services.
 *
 * Subclasses must implement the platform-specific synthesis logic
 * while inheriting callback management and status tracking.
 */
export abstract class TTSService {
  protected _status: SpeechStatus = 'idle';
  protected _callbacks: TTSCallback[] = [];

  /**
   * Request that the TTS engine speak the given text.
   *
   * @param text - The text to synthesize and speak.
   * @returns A promise that resolves when the speech request has been queued.
   */
  abstract speak(text: string): Promise<void>;

  /**
   * Request that the TTS engine stop speaking immediately.
   *
   * @returns A promise that resolves when the stop action completes.
   */
  abstract stop(): Promise<void>;

  /**
   * Returns the current speech status.
   *
   * @returns The current {@link SpeechStatus}.
   */
  abstract getStatus(): SpeechStatus;

  /**
   * Returns whether the underlying TTS engine is available.
   *
   * @returns `true` if speech synthesis is supported in the current environment.
   */
  abstract isAvailable(): boolean;

  /**
   * Registers a callback to be invoked on every status change.
   *
   * @param callback - The callback to register.
   */
  addOnStatusChange(callback: TTSCallback): void {
    this._callbacks.push(callback);
  }

  /**
   * Removes a previously registered status-change callback.
   *
   * @param callback - The callback to remove.
   */
  removeOnStatusChange(callback: TTSCallback): void {
    const index = this._callbacks.indexOf(callback);
    if (index !== -1) {
      this._callbacks.splice(index, 1);
    }
  }

  /**
   * Cleans up resources. Subclasses may override for custom cleanup.
   *
   * Default is a no-op for implementations that don't need cleanup.
   */
  cleanup(): void {
    // No-op base implementation
  }

  /**
   * Updates the internal status and notifies all registered callbacks.
   *
   * @param newStatus - The new status to set.
   */
  protected _setStatus(newStatus: SpeechStatus): void {
    this._status = newStatus;
    for (const callback of this._callbacks) {
      try {
        callback(newStatus);
      } catch {
        // Ignore callback errors so other listeners are still notified.
      }
    }
  }
}
