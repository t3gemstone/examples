
#ifdef __cplusplus
extern "C" {
#endif
#include <kernel/dpl/DebugP.h>
#ifdef __cplusplus
}
#endif

#include <dsplib.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include <drivers/hw_include/csl_clec.h>


#ifdef __cplusplus
extern "C" {
#endif
int32_t dsplib_test_main()
{
   DebugP_log((char *)"\r\n--------------------------------------------------");
   DebugP_log((char *)"\r\n            T3 Gemstone DSPLIB Test              ");
   DebugP_log((char *)"\r\n--------------------------------------------------\r\n");


   // Setup input and output buffers for single- and double-precision datatypes
   float in0[] = {0.71649936, 0.13543484, 0.50923542, 0.54119591, 0.19242506, 0.38308575, 0.56363197,
                  0.24567145, 0.05629663, 0.99152828, 0.4799542,  0.97309674, 0.79839982, 0.06691247};

   float in1[] = {0.,         0.78539816, 1.57079633, 2.35619449, 3.14159265, 3.92699082, 4.71238898,
                  5.49778714, 0.,         0.78539816, 1.57079633, 2.35619449, 3.14159265, 3.92699082};

   float out[] = {0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0.};

   uint32_t size = 14;

   // handles and struct for call to kernel
   DSPLIB_STATUS       status;
   DSPLIB_add_InitArgs kerInitArgs;
   int32_t             handleSize = DSPLIB_add_getHandleSize(&kerInitArgs);
   DSPLIB_kernelHandle handle     = malloc(handleSize);

   DSPLIB_bufParams1D_t bufParamsIn, bufParamsOut;

   // fill in input and output buffer parameters
   bufParamsIn.data_type = DSPLIB_FLOAT32;
   bufParamsIn.dim_x     = size;

   bufParamsOut.data_type = DSPLIB_FLOAT32;
   bufParamsOut.dim_x     = size;

   kerInitArgs.dataSize  = size;
   kerInitArgs.funcStyle = DSPLIB_FUNCTION_OPTIMIZED;

   status = DSPLIB_SUCCESS;

   // init checkparams
   // if (status == DSPLIB_SUCCESS)
   //    status = DSPLIB_add_init_checkParams(handle, &bufParamsIn, &bufParamsOut, &kerInitArgs);

   // init
   if (status == DSPLIB_SUCCESS)
      status = DSPLIB_add_init(handle, &bufParamsIn, &bufParamsOut, &kerInitArgs);

   // exec checkparams
   // if (status == DSPLIB_SUCCESS)
   //    DSPLIB_add_exec_checkParams(handle, in0, in1, out);

   // exec
   if (status == DSPLIB_SUCCESS)
      status = DSPLIB_add_exec(handle, in0, in1, out);

   // print results
   for (size_t c = 0; c < size; c++) {
       DebugP_log((char *)"\r\n%10g + %10g = %10g", in0[c], in1[c], out[c]);
   }

   return 0;

}
#ifdef __cplusplus
}
#endif
