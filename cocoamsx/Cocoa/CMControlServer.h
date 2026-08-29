#import <Foundation/Foundation.h>

@class CMEmulatorController;

@interface CMControlServer : NSObject
+ (CMControlServer *)sharedServer;
- (void)startWithEmulator:(CMEmulatorController *)emulator;
- (void)stop;
@end
