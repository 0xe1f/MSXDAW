/*****************************************************************************
 **
 ** Research-display JSON config. Loaded at launch; live keys can hot-reload.
 **
 ******************************************************************************/
#import <Foundation/Foundation.h>

@interface CMConfig : NSObject

+ (CMConfig *)sharedConfig;

@property (nonatomic, copy, readonly) NSString *machine;
@property (nonatomic, assign, readonly) NSInteger volume;
@property (nonatomic, assign, readonly) NSInteger scale;
@property (nonatomic, assign) BOOL accelerated;
@property (nonatomic, copy, readonly) NSString *vdpSync; /* "60hz" */
@property (nonatomic, assign, readonly) NSInteger speed;
@property (nonatomic, copy, readonly) NSString *socketPath;
@property (nonatomic, copy, readonly) NSString *snapRange;
@property (nonatomic, copy, readonly) NSString *configPath;

- (void)reload;
- (void)setAcceleratedFromString:(NSString *)onOff;

@end
