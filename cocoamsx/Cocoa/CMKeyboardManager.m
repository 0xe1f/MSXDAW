#import "CMKeyboardManager.h"

static CMKeyboardManager *_keyboardManager = nil;

@implementation CMKeyboardManager
{
    NSMutableArray *observers;
    NSObject *observerLock;
}

+ (CMKeyboardManager *)sharedInstance
{
    if (!_keyboardManager)
        _keyboardManager = [[CMKeyboardManager alloc] init];
    return _keyboardManager;
}

- (id)init
{
    if ((self = [super init])) {
        observerLock = [[NSObject alloc] init];
        observers = [[NSMutableArray alloc] init];
    }
    return self;
}

- (void)injectKeyCode:(NSInteger)keyCode isDown:(BOOL)isDown
{
    CMKeyEventData *event = [[CMKeyEventData alloc] init];
    [event setScanCode:keyCode];
    [event setKeyCode:keyCode];
    @synchronized (observerLock) {
        [observers enumerateObjectsUsingBlock:^(id obj, NSUInteger idx, BOOL *stop) {
            [obj keyStateChanged:event isDown:isDown];
        }];
    }
}

- (void)addObserver:(id<CMKeyboardEventDelegate>)observer
{
    @synchronized (observerLock) {
        [observers addObject:observer];
    }
}

- (void)removeObserver:(id<CMKeyboardEventDelegate>)observer
{
    @synchronized (observerLock) {
        [observers removeObject:observer];
    }
}

@end
