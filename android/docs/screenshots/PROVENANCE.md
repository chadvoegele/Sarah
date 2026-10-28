# Historical screenshot provenance

These two PNGs are authentic historical SARAH Android emulator captures from the
owner-controlled code3 launcher-icon review, not artwork renders or reconstructed UI.
They show `com.serexe.sarah`, versionCode `3`, versionName `0.1.2-review`.
The historical review records installed APK SHA-256:

```text
f6a493e30d6612ba96713d6543f5e7e59c98d24ec0f8472cc8bc13cb107fcc7e
```

## Images

### `code3-tap-to-talk.png`

Foreground tap-to-talk screen, Ready / Connected, with deliberately seeded synthetic transcript and reply.

- Original historical capture filename: `final-relaunch.png`.
- Dimensions: 2184 × 1968 pixels.
- SHA-256: `e2bc83fbce8669dce3693cd32fe6d8151dc076995ea0a8dd08e7f4a782da4449`.
- Publication bytes are identical to the original capture.
- No cropping, redraw, synthesized UI, compositing, or redaction.
- PNG metadata contains only the standard sRGB color-space marker; no textual/private metadata.

### `code3-clear-pairing.png`

Clear local pairing confirmation opened from Connection settings; behind it is the same seeded synthetic transcript. No reset was performed.

- Original historical capture filename: `connection-settings.png`.
- Dimensions: 2184 × 1968 pixels.
- SHA-256: `df595212217a7d7d7e5ad705b99c79dc9119a941cdd148df07e242cfd236c7cc`.
- Publication bytes are identical to the original capture.
- No cropping, redraw, synthesized UI, compositing, or redaction.
- PNG metadata contains only the standard sRGB color-space marker; no textual/private metadata.

## Privacy and limitations

Visual review found no private endpoint, token, account identifier, or personal
conversation. Visible transcript/reply explicitly say “Synthetic audio fixture”.
The pairing dialog contains explanatory product text, not a token value.
Original captures remain preserved privately outside the public repository.

These are pre-wake foreground tap-to-talk screens. The connected state and seeded
text do not establish live pairing, microphone capture, bridge reachability, or a
successful network voice exchange. They are not code8 screenshots, current worker
screenshots, or physical-device evidence. No new build, test, emulator interaction,
or installation was performed for this publication update.

## Icon provenance

Owner-approved house-and-luminous-S-orb artwork is preserved at
`artwork/launcher-artwork-original.png`, SHA-256:

```text
65a244ea8a20b697af8edb5175ec8a813aba7590fb6a120d65218bc010a22e4f
```

Read-only comparison against current icon resource/artwork files found the original
and all 18 launcher files byte-identical to the restored code3 source. Therefore
no icon files were changed. Displaying it here does not imply a rebuilt APK or
that the historical code3 source contains later assistant features.
