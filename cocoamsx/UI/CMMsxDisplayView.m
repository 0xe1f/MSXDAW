/*****************************************************************************
 ** Research display: CALayer (accelerated) or CPU drawRect present.
 ** Keyboard is AppKit first-responder only — no IOHID / Input Monitoring.
 ******************************************************************************/
#import "CMMsxDisplayView.h"
#import "CMEmulatorController.h"
#import "CMFrameCounter.h"
#import "CMKeyboardManager.h"
#import "CMConfig.h"
#import "CMPreferences.h"

#import <QuartzCore/QuartzCore.h>

#ifdef DISASMTRACE
void disasmTraceRequestSnapshot(void);
void disasmTraceToggleAutoSnap(void);
int  disasmTraceAutoSnapActive(void);
void disasmTraceAutoSnapTick(void);
#define CM_VK_F8 0x64
#define CM_VK_F9 0x65
#endif

#include "Properties.h"
#include "VideoRender.h"
#include "FrameBuffer.h"
#include "ArchNotifications.h"

#define ACTUAL_WIDTH 272
#define BUFFER_WIDTH 320
#define HEIGHT       240
#define DEPTH        32
#define ZOOM         2
#define HIDE_CURSOR_TIMEOUT_SECONDS 1.0f

@interface CMMsxDisplayView ()
- (void)renderIntoBuffer;
- (void)presentAccelerated;
- (void)presentSoftware;
- (void)handleMouseAction:(NSEvent *)theEvent;
- (void)applyAcceleratedMode;
- (CGImageRef)newImageFromPixels;
@end

@implementation CMMsxDisplayView
{
    UInt32 borderColor;
    CGFloat framesPerSecond;
    CMFrameCounter *frameCounter;
    CFAbsoluteTime lastMouseAction;
    NSPoint lastCursorPosition;
    BOOL cursorVisible;
    BOOL accelerated;
    UInt32 *pixels;
    int pixelWidth;
    int pixelHeight;
    int pitch;
    NSView *recordDot;
}

#pragma mark - Init

- (void)dealloc
{
    free(pixels);
    pixels = NULL;
}

- (void)awakeFromNib
{
    pixelWidth = BUFFER_WIDTH * ZOOM;
    pixelHeight = HEIGHT * ZOOM;
    pitch = pixelWidth * (int)sizeof(UInt32);
    pixels = (UInt32 *)calloc((size_t)pixelWidth * (size_t)pixelHeight, sizeof(UInt32));

    accelerated = [CMConfig sharedConfig].accelerated;
    [self applyAcceleratedMode];

    [self.window setAcceptsMouseMovedEvents:YES];
    frameCounter = [[CMFrameCounter alloc] init];
    lastMouseAction = CFAbsoluteTimeGetCurrent();
    cursorVisible = YES;
    lastCursorPosition = NSMakePoint(-1, -1);

    recordDot = [[NSView alloc] initWithFrame:NSMakeRect(12, self.bounds.size.height - 30, 18, 18)];
    recordDot.wantsLayer = YES;
    recordDot.layer.backgroundColor = [[NSColor colorWithCalibratedRed:1 green:0.15 blue:0.1 alpha:1] CGColor];
    recordDot.layer.cornerRadius = 2;
    recordDot.autoresizingMask = NSViewMinYMargin | NSViewMaxXMargin;
    recordDot.hidden = YES;
    [self addSubview:recordDot];
}

- (void)viewDidMoveToWindow
{
    [super viewDidMoveToWindow];
    [[self window] makeFirstResponder:self];
}

- (void)applyAcceleratedMode
{
    self.wantsLayer = accelerated;
    if (accelerated) {
        self.layer.opaque = YES;
        self.layer.magnificationFilter = kCAFilterNearest;
        self.layer.minificationFilter = kCAFilterNearest;
        self.layer.contentsGravity = kCAGravityResize;
    } else {
        self.layer.contents = nil;
    }
    [self setNeedsDisplay:YES];
}

- (void)setAccelerated:(BOOL)value
{
    if (accelerated == value)
        return;
    accelerated = value;
    [self applyAcceleratedMode];
}

- (BOOL)isAccelerated
{
    return accelerated;
}

#pragma mark - Keys (responder chain; window-focused)

- (BOOL)acceptsFirstResponder
{
    return YES;
}

- (void)keyDown:(NSEvent *)theEvent
{
    unsigned short kc = [theEvent keyCode];
#ifdef DISASMTRACE
    if (kc == CM_VK_F9) {
        disasmTraceRequestSnapshot();
        return;
    }
    if (kc == CM_VK_F8) {
        if (![theEvent isARepeat])
            disasmTraceToggleAutoSnap();
        return;
    }
#endif
    if (![theEvent isARepeat])
        [[CMKeyboardManager sharedInstance] injectKeyCode:kc isDown:YES];
}

- (void)keyUp:(NSEvent *)theEvent
{
    [[CMKeyboardManager sharedInstance] injectKeyCode:[theEvent keyCode] isDown:NO];
}

- (void)flagsChanged:(NSEvent *)theEvent
{
    unsigned short kc = [theEvent keyCode];
    NSEventModifierFlags flags = [theEvent modifierFlags];
    BOOL down;
    switch (kc) {
        case 56: case 60: down = (flags & NSEventModifierFlagShift)   != 0; break;
        case 59: case 62: down = (flags & NSEventModifierFlagControl) != 0; break;
        case 58: case 61: down = (flags & NSEventModifierFlagOption)  != 0; break;
        case 55: case 54: down = (flags & NSEventModifierFlagCommand) != 0; break;
        case 57:          down = (flags & NSEventModifierFlagCapsLock) != 0; break;
        default: return;
    }
    [[CMKeyboardManager sharedInstance] injectKeyCode:kc isDown:down];
}

- (void)cancelOperation:(id)sender
{
}

#pragma mark - Mouse

- (void)mouseMoved:(NSEvent *)theEvent
{
    [self handleMouseAction:theEvent];
    [[emulator mouse] mouseMoved:theEvent withinView:self];
}

- (void)mouseDragged:(NSEvent *)theEvent
{
    [self handleMouseAction:theEvent];
    [[emulator mouse] mouseMoved:theEvent withinView:self];
}

- (void)mouseDown:(NSEvent *)theEvent
{
    [self handleMouseAction:theEvent];
    [[emulator mouse] mouseDown:theEvent withinView:self];
}

- (void)mouseUp:(NSEvent *)theEvent
{
    [self handleMouseAction:theEvent];
    [[emulator mouse] mouseUp:theEvent withinView:self];
}

- (void)rightMouseDown:(NSEvent *)theEvent
{
    [self handleMouseAction:theEvent];
    [[emulator mouse] rightMouseDown:theEvent];
}

- (void)rightMouseUp:(NSEvent *)theEvent
{
    [self handleMouseAction:theEvent];
    [[emulator mouse] rightMouseUp:theEvent];
}

- (void)handleMouseAction:(NSEvent *)theEvent
{
    lastMouseAction = CFAbsoluteTimeGetCurrent();
    lastCursorPosition = [self convertPoint:[theEvent locationInWindow] fromView:nil];
    if (!cursorVisible) {
        cursorVisible = YES;
        [[emulator mouse] showCursor:YES];
    }
}

#pragma mark - Present

- (void)drawRect:(NSRect)dirtyRect
{
    if (!accelerated)
        [self presentFrame];
}

- (void)presentFrame
{
    if ([[self window] isKeyWindow] && NSPointInRect(lastCursorPosition, [self bounds])) {
        CFAbsoluteTime interval = CFAbsoluteTimeGetCurrent() - lastMouseAction;
        if (cursorVisible && interval > HIDE_CURSOR_TIMEOUT_SECONDS && CMGetBoolPref(@"autohideCursor")) {
            [[emulator mouse] showCursor:NO];
            cursorVisible = NO;
        }
    }

    if (!emulator.isInitialized)
        return;

    framesPerSecond = [frameCounter update];
    [emulator updateFps:framesPerSecond];

    [self renderIntoBuffer];

#ifdef DISASMTRACE
    disasmTraceAutoSnapTick();
    BOOL rec = disasmTraceAutoSnapActive();
    recordDot.hidden = !rec;
    if (rec) {
        static unsigned blink = 0;
        recordDot.alphaValue = ((++blink % 40) < 24) ? 1.0 : 0.15;
    }
#else
    recordDot.hidden = YES;
#endif

    if (accelerated)
        [self presentAccelerated];
    else
        [self presentSoftware];
}

- (void)renderIntoBuffer
{
    if (!pixels)
        return;

    Properties *properties = emulator.properties;
    Video *video = emulator.video;
    FrameBuffer *frameBuffer = frameBufferFlipViewFrame(
        properties->emulation.syncMethod == P_EMU_SYNCTOVBLANKASYNC);
    if (frameBuffer == NULL)
        frameBuffer = frameBufferGetWhiteNoiseFrame();

    int borderWidth = (BUFFER_WIDTH - frameBuffer->maxWidth) * ZOOM / 2;
    UInt8 *dpy = (UInt8 *)pixels;

    video->palMode = VIDEO_PAL_FAST;
    videoRender(video, frameBuffer, DEPTH, ZOOM,
                dpy + borderWidth * (int)sizeof(UInt32), 0, pitch, -1);

    UInt32 bgColor = pixels[borderWidth];
    if (bgColor != borderColor) {
        borderColor = bgColor;
        if ([self->_delegate respondsToSelector:@selector(msxDisplay:borderColorChanged:)]) {
            [self->_delegate msxDisplay:self borderColorChanged:[self borderColor]];
        }
    }

    if (borderWidth > 0) {
        UInt8 *row = dpy;
        int h = pixelHeight;
        int bw = borderWidth * (int)sizeof(UInt32);
        while (h--) {
            memset(row, 0, (size_t)bw);
            memset(row + pitch - bw, 0, (size_t)bw);
            row += pitch;
        }
    }
}

- (CGImageRef)newImageFromPixels
{
    if (!pixels)
        return NULL;
    CGColorSpaceRef cs = CGColorSpaceCreateDeviceRGB();
    CGDataProviderRef prov = CGDataProviderCreateWithData(NULL, pixels,
        (size_t)pitch * (size_t)pixelHeight, NULL);
    /* Live buffer is RGBA bytes (same as the old GL_RGBA upload). */
    CGImageRef img = CGImageCreate((size_t)pixelWidth, (size_t)pixelHeight,
                                   8, 32, (size_t)pitch, cs,
                                   kCGImageAlphaNoneSkipLast | kCGBitmapByteOrder32Big,
                                   prov, NULL, false, kCGRenderingIntentDefault);
    CGDataProviderRelease(prov);
    CGColorSpaceRelease(cs);
    return img;
}

- (void)presentAccelerated
{
    CGImageRef img = [self newImageFromPixels];
    if (!img)
        return;
    self.layer.contents = (__bridge id)img;
    CGImageRelease(img);
}

- (void)presentSoftware
{
    CGImageRef img = [self newImageFromPixels];
    if (!img)
        return;
    NSRect bounds = [self bounds];
    CGContextRef ctx = [[NSGraphicsContext currentContext] CGContext];
    if (ctx) {
        CGContextSaveGState(ctx);
        CGContextSetInterpolationQuality(ctx, kCGInterpolationNone);
        /* Unflipped NSView: CGImage row 0 is the top of the FAST buffer. */
        CGContextDrawImage(ctx, NSRectToCGRect(bounds), img);
        CGContextRestoreGState(ctx);
    }
    CGImageRelease(img);
}

- (CGFloat)framesPerSecond
{
    return framesPerSecond;
}

- (NSColor *)borderColor
{
    return [NSColor colorWithCalibratedRed:(borderColor & 0xff) / 255.0
                                     green:((borderColor >> 8) & 0xff) / 255.0
                                      blue:((borderColor >> 16) & 0xff) / 255.0
                                     alpha:1.0];
}

#pragma mark - blueMSX

extern CMEmulatorController *theEmulator;

int archUpdateEmuDisplay(int syncMode)
{
    @autoreleasepool {
        CMMsxDisplayView *screen = theEmulator.screen;
        if ([NSThread isMainThread]) {
            if (screen.isAccelerated)
                [screen presentFrame];
            else
                screen.needsDisplay = YES;
        } else {
            dispatch_async(dispatch_get_main_queue(), ^{
                if (screen.isAccelerated)
                    [screen presentFrame];
                else
                    screen.needsDisplay = YES;
            });
        }
    }
    return 1;
}

void archUpdateWindow()
{
}

- (NSImage *)captureScreen:(BOOL)large
{
    NSInteger zoom = large ? 2 : 1;
    NSInteger width = BUFFER_WIDTH * zoom;
    NSInteger height = HEIGHT * zoom;
    NSInteger rowBytes = width * sizeof(UInt32);
    UInt32 *raw = malloc((size_t)rowBytes * (size_t)height);
    if (!raw)
        return nil;

    Video *copy = videoCopy(emulator.video);
    if (!copy) {
        free(raw);
        return nil;
    }
    copy->palMode = VIDEO_PAL_FAST;
    copy->scanLinesEnable = 0;
    copy->colorSaturationEnable = 0;

    FrameBuffer *frameBuffer = frameBufferGetViewFrame();
    if (frameBuffer == NULL || frameBuffer->maxWidth <= 0 || frameBuffer->lines <= 0) {
        free(raw);
        videoDestroy(copy);
        return nil;
    }

    videoRender(copy, frameBuffer, 32, (int)zoom, raw, 0, (int)rowBytes, 0);
    videoDestroy(copy);

    for (NSInteger i = width * height - 1; i >= 0; i--) {
        UInt8 r = raw[i] & 0xff;
        UInt8 g = (raw[i] & 0xff00) >> 8;
        UInt8 b = (raw[i] & 0xff0000) >> 16;
        raw[i] = r | (g << 8) | (b << 16) | 0xff000000;
    }

    NSBitmapImageRep *rep = [[NSBitmapImageRep alloc]
        initWithBitmapDataPlanes:NULL
                      pixelsWide:frameBuffer->maxWidth * zoom
                      pixelsHigh:height
                   bitsPerSample:8
                 samplesPerPixel:4
                        hasAlpha:YES
                        isPlanar:NO
                  colorSpaceName:NSCalibratedRGBColorSpace
                    bitmapFormat:NSBitmapFormatAlphaNonpremultiplied
                     bytesPerRow:rowBytes
                    bitsPerPixel:0];
    memcpy([rep bitmapData], raw, (size_t)rowBytes * (size_t)height);
    NSImage *image = [[NSImage alloc] initWithSize:NSMakeSize(width, height)];
    [image addRepresentation:rep];
    free(raw);
    return image;
}

void *archScreenCapture(ScreenCaptureType type, int *bitmapSize, int onlyBmp)
{
    void *bytes = NULL;
    *bitmapSize = 0;
    @autoreleasepool {
        NSImage *image = [theEmulator.screen captureScreen:NO];
        if (image && [image representations].count > 0) {
            NSBitmapImageRep *rep = (NSBitmapImageRep *)[[image representations] firstObject];
            NSData *pngData = [rep representationUsingType:NSBitmapImageFileTypePNG properties:@{}];
            *bitmapSize = (int)pngData.length;
            bytes = malloc((size_t)*bitmapSize);
            memcpy(bytes, [pngData bytes], (size_t)*bitmapSize);
        }
    }
    return bytes;
}

@end
