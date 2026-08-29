#import <Cocoa/Cocoa.h>

@class CMEmulatorController;
@class CMMsxDisplayView;

@protocol CMMsxDisplayViewDelegate <NSObject>
@optional
- (void) msxDisplay:(CMMsxDisplayView *) display
 borderColorChanged:(NSColor *) borderColor;
@end

@interface CMMsxDisplayView : NSView
{
    IBOutlet CMEmulatorController *emulator;
}

@property (nonatomic, weak) IBOutlet id<CMMsxDisplayViewDelegate> delegate;

- (CGFloat) framesPerSecond;
- (NSImage *) captureScreen:(BOOL) large;
- (NSColor *) borderColor;
- (void) presentFrame;
- (void) setAccelerated:(BOOL) accelerated;
- (BOOL) isAccelerated;

@end
