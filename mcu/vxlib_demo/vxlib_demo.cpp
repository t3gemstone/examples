
#ifdef __cplusplus
extern "C" {
#endif
#include <kernel/dpl/DebugP.h>
#ifdef __cplusplus
}
#endif

// include VXLIB
#include <VXLIB_bufParams.h>
#include <VXLIB_types.h>
#include <vxlib.h>

#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#define height (5)
#define width (5)
#define filterDim (3)

#ifdef __cplusplus
extern "C" {
#endif

int32_t vxlib_test_main()
{
   DebugP_log((char *)"Init local vars\r\n");

   DebugP_log((char *)"\r\n--------------------------------------------------");
   DebugP_log((char *)"\r\n            T3 Gemstone VXLIB Test              ");
   DebugP_log((char *)"\r\n--------------------------------------------------\r\n");




   /*****************************************/
   /*          Non-Padded Example           */
   /*****************************************/

   // input image dimension must be greater than or equal to filter dimensions
   assert((height >= filterDim) && (width >= filterDim));

   // output image dimension calculation
   uint32_t outHeight = height - filterDim + 1;
   uint32_t outWidth  = width - filterDim + 1;

   // clang-format off
    
  uint8_t in_u8[] = {1,  2,  3,  4,  5,
		     6,  7,  8,  9,  10,
		     11, 12, 13, 14, 15,
		     16, 17, 18, 19, 20,
		     21, 22, 23, 24, 25};


   uint8_t out_u8[] = {0, 0, 0,
		       0, 0, 0,
		       0, 0, 0};

   // clang-format on

   // handles and struct for call to kernel
   VXLIB_STATUS       status;
   VXLIB_box_InitArgs kerInitArgs;
   int32_t            handleSize = VXLIB_box_getHandleSize(&kerInitArgs);
   VXLIB_kernelHandle handle     = malloc(handleSize);

   VXLIB_bufParams2D_t bufParamsIn, bufParamsOut;

   bufParamsIn.data_type = VXLIB_UINT8;
   bufParamsIn.dim_x     = width;
   bufParamsIn.dim_y     = height;
   bufParamsIn.stride_y  = width * sizeof(uint8_t);

   bufParamsOut.data_type = VXLIB_UINT8;
   bufParamsOut.dim_x     = outWidth;
   bufParamsOut.dim_y     = outHeight;
   bufParamsOut.stride_y  = outWidth * sizeof(uint8_t);

   kerInitArgs.padLeft    = 0;
   kerInitArgs.padRight   = 0;
   kerInitArgs.padTop     = 0;
   kerInitArgs.padBottom  = 0;
   kerInitArgs.filterSize = filterDim;

   kerInitArgs.funcStyle = VXLIB_FUNCTION_OPTIMIZED;

   status = VXLIB_SUCCESS;

   // init checkparams
   status = VXLIB_box_init_checkParams(handle, &bufParamsIn, &bufParamsOut, &kerInitArgs);

   // init
   if (status == VXLIB_SUCCESS)
      status = VXLIB_box_init(handle, &bufParamsIn, &bufParamsOut, &kerInitArgs);
   else {
       DebugP_log((char *)"\r\nInit checkparams failed: %d\n\r", status);
      return 0;
   }

   // exec checkparams
   VXLIB_box_exec_checkParams(handle, in_u8, out_u8);

   // exec
   if (status == VXLIB_SUCCESS)
      status = VXLIB_box_exec(handle, in_u8, out_u8);
   else {
       DebugP_log((char *)"\r\nExec checkparams failed: %d\n\r", status);
      return 0;
   }

   // print results
   DebugP_log((char *)"\r\nNon-Padded 3x3 Box Filter\n\r");
   DebugP_log((char *)"\r\nInput Image\n\r");

   for (size_t i = 0; i < height; i++) {
      DebugP_log((char *)"\r\n");
      for (size_t j = 0; j < width; j++) {
         DebugP_log((char *)"%d, ", in_u8[i * width + j]);
      }
   }

   DebugP_log((char *)"\r\n");

   DebugP_log((char *)"\r\nOutput Image\r\n");

   for (size_t i = 0; i < outHeight; i++) {
      DebugP_log((char *)"\r\n");
      for (size_t j = 0; j < outWidth; j++) {
         DebugP_log((char *)"%d, ", out_u8[i * outWidth + j]);
      }
   }
   DebugP_log((char *)"\r\n");

   free(handle);

   return 0;

}
#ifdef __cplusplus
}
#endif
