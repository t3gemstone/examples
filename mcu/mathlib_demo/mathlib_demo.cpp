
#ifdef __cplusplus
extern "C" {
#endif
#include <kernel/dpl/DebugP.h>
#ifdef __cplusplus
}
#endif

#include <mathlib.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include <drivers/hw_include/csl_clec.h>


#ifdef __cplusplus
extern "C" {
#endif
int32_t mathlib_test_main()
{
   DebugP_log((char *)"\r\n--------------------------------------------------");
   DebugP_log((char *)"\r\n            T3 Gemstone MATHLIB Test              ");
   DebugP_log((char *)"\r\n--------------------------------------------------\r\n");


   // Setup input and output buffers for single precision datatypes
   float inSp[] = {1.,          0.97094182,  0.88545603,  0.74851075,  0.56806475,  0.35460489,  0.12053668,
                   -0.12053668, -0.35460489, -0.56806475, -0.74851075, -0.88545603, -0.97094182, -1.};

   float outSp[] = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};

   size_t length = 14;

   // call single-precision version of MATHLIB_acos
   MATHLIB_acos(length, inSp, outSp);
   // print results
   for (size_t c = 0; c < length; c++) {
      printf("acos(%10g) = %10g\n", inSp[c], outSp[c]);
   }

   // single precision C interface
   MATHLIB_acos_sp(length, inSp, outSp);
   // print results
   for (size_t c = 0; c < length; c++) {
      printf("acos(%10g) = %10g\n", inSp[c], outSp[c]);
   }


   return 0;

}
#ifdef __cplusplus
}
#endif
