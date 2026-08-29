#import <Foundation/Foundation.h>
#import "CMKeyEventData.h"

@protocol CMKeyboardEventDelegate
@required
- (void)keyStateChanged:(CMKeyEventData *)event
                 isDown:(BOOL)isDown;
@end

@interface CMKeyboardManager : NSObject

+ (CMKeyboardManager *)sharedInstance;

- (void)addObserver:(id<CMKeyboardEventDelegate>)observer;
- (void)removeObserver:(id<CMKeyboardEventDelegate>)observer;

/* AppKit responder / agent inject. keyCode is a macOS virtual key code. */
- (void)injectKeyCode:(NSInteger)keyCode isDown:(BOOL)isDown;

@end
